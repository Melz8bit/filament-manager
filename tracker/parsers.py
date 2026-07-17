import zipfile
import xml.etree.ElementTree as ET


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

            material = elem.get("type", "")
            results.append(
                {
                    "grams": grams,
                    "hex": hex_val,
                    "material": material,
                }
            )

        return results
