import re
import zipfile
import xml.etree.ElementTree as ET

_E_VALUE_RE = re.compile(r"E(-?\d*\.?\d+)")
_TOOL_CHANGE_RE = re.compile(r"^T(\d+)")


def parse_gcode(file_obj):
    lines = file_obj.read().decode("utf-8", errors="ignore").splitlines()

    hex_list = []
    material_list = []
    grams_by_slot = {}  # slot index -> cumulative grams across all plates

    for line in lines:
        line = line.strip()

        if line.startswith("; filament used [g]"):
            plate_grams = [x.strip() for x in line.split("=")[1].split(",")]
            for i, g in enumerate(plate_grams):
                try:
                    grams_by_slot[i] = grams_by_slot.get(i, 0.0) + float(g)
                except ValueError:
                    pass
        elif line.startswith("; filament_colour") and not hex_list:
            hex_list = [x.strip() for x in line.split("=")[1].split(",")]
        elif line.startswith("; filament_type") and not material_list:
            material_list = [x.strip() for x in line.split("=")[1].split(",")]

    results = []
    for i, (hex_val, material) in enumerate(zip(hex_list, material_list)):
        grams = grams_by_slot.get(i, 0.0)
        if grams == 0.0:
            continue
        if not hex_val.startswith("#"):
            hex_val = "#" + hex_val
        hex_val = hex_val[:7]  # drop alpha channel if present (RRGGBBAA -> RRGGBB)
        results.append({"grams": grams, "hex": hex_val, "material": material})

    return results


def parse_3mf(file_obj):
    with zipfile.ZipFile(file_obj) as z:
        names = z.namelist()

        config_name = next(
            (n for n in names if n.lower().endswith("slice_info.config")),
            None,
        )
        if config_name is None:
            return []

        raw = z.read(config_name)
        root = ET.fromstring(raw)

        results = []
        for elem in root.iter():
            used_g = elem.get("used_g")
            if used_g is None:
                continue

            grams = float(used_g)
            if grams == 0.0:
                continue

            hex_val = elem.get("color", "")
            if not hex_val.startswith("#"):
                hex_val = "#" + hex_val
            hex_val = hex_val[:7]  # drop alpha channel if present (RRGGBBAA -> RRGGBB)

            material = elem.get("type", "")
            results.append(
                {
                    "grams": grams,
                    "hex": hex_val,
                    "material": material,
                }
            )

        return results


def _ordered_filaments_3mf(z):
    config_name = next((n for n in z.namelist() if n.lower().endswith("slice_info.config")), None)
    if config_name is None:
        return []
    root = ET.fromstring(z.read(config_name))
    filaments = sorted(root.iter("filament"), key=lambda el: int(el.get("id", 0)))
    ordered = []
    for el in filaments:
        hex_val = el.get("color", "")
        if not hex_val.startswith("#"):
            hex_val = "#" + hex_val
        ordered.append((hex_val[:7], el.get("type", "")))
    return ordered


def _ordered_filaments_gcode_header(lines):
    hex_list, material_list = [], []
    for line in lines:
        line = line.strip()
        if line.startswith("; filament_colour") and not hex_list:
            hex_list = [x.strip() for x in line.split("=")[1].split(",")]
        elif line.startswith("; filament_type") and not material_list:
            material_list = [x.strip() for x in line.split("=")[1].split(",")]
        if hex_list and material_list:
            break
    ordered = []
    for hex_val, material in zip(hex_list, material_list):
        if not hex_val.startswith("#"):
            hex_val = "#" + hex_val
        ordered.append((hex_val[:7], material))
    return ordered


def estimate_remaining_by_layer(file_obj, source, failed_layer):
    """
    Estimate, per (hex, material) filament, what fraction of its total usage had NOT
    yet been extruded when a print was cancelled partway through `failed_layer`.

    Walks the embedded (.3mf) or raw (.gcode) gcode body, tracking real extrusion (E)
    moves per active tool (T0/T1/...) between "; CHANGE_LAYER" markers — this reflects
    actual filament consumed rather than a naive layer-count fraction, so colors used
    unevenly across the print (e.g. a logo near the top) are credited correctly.

    Returns (remaining_by_key, total_layers):
      - total_layers: layers found via CHANGE_LAYER markers; 0 if this file has no
        per-layer gcode data to work from (caller should fall back to a percent-based
        estimate instead).
      - remaining_by_key: dict mapping (hex, material) -> remaining fraction (0..1);
        None if `failed_layer` is out of range for this print (caller should re-prompt
        with a valid range using `total_layers`).
    """
    if source == "threemf":
        with zipfile.ZipFile(file_obj) as z:
            ordered = _ordered_filaments_3mf(z)
            gcode_name = next((n for n in z.namelist() if n.lower().endswith(".gcode")), None)
            if not ordered or gcode_name is None:
                return None, 0
            lines = z.read(gcode_name).decode("utf-8", errors="ignore").splitlines()
    else:
        lines = file_obj.read().decode("utf-8", errors="ignore").splitlines()
        ordered = _ordered_filaments_gcode_header(lines)
        if not ordered:
            return None, 0

    num_tools = len(ordered)
    cumulative = [0.0] * num_tools
    snapshot = None
    current_tool = 0
    relative_mode = False
    last_e = 0.0
    layer_index = 0

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if s == "; CHANGE_LAYER":
            layer_index += 1
            if layer_index == failed_layer and snapshot is None:
                snapshot = cumulative.copy()
            continue

        first = s[0]

        if first == "M":
            if s == "M83":
                relative_mode = True
            elif s == "M82":
                relative_mode = False
            continue

        if first == "T":
            m = _TOOL_CHANGE_RE.match(s)
            if m:
                idx = int(m.group(1))
                if 0 <= idx < num_tools:
                    current_tool = idx
            continue

        if s.startswith("G92") and "E" in s:
            m = _E_VALUE_RE.search(s)
            if m:
                last_e = float(m.group(1))
            continue

        if first == "G" and (s.startswith("G1 ") or s.startswith("G0 ")):
            m = _E_VALUE_RE.search(s)
            if m:
                e_val = float(m.group(1))
                if relative_mode:
                    cumulative[current_tool] += e_val
                else:
                    cumulative[current_tool] += e_val - last_e
                    last_e = e_val

    total_layers = layer_index
    if total_layers == 0:
        return None, 0
    if snapshot is None:
        return None, total_layers

    remaining_by_key = {}
    for i, key in enumerate(ordered):
        total = cumulative[i]
        if total <= 0:
            remaining_by_key[key] = 0.0
        else:
            remaining_by_key[key] = max(0.0, min(1.0, 1 - (snapshot[i] / total)))

    return remaining_by_key, total_layers
