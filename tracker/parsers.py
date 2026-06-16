import zipfile
import xml.etree.ElementTree as ET


def parse_gcode(file_obj):
    lines = file_obj.read().decode("utf-8", errors="ignore").splitlines()

    grams_list = []
    hex_list = []
    material_list = []

    for line in lines[:200]:
        line = line.strip()

        if line.startswith("; filament used [g]"):
            grams_list = [x.strip() for x in line.split("=")[1].split(",")]
        elif line.startswith("; filament_colour"):
            hex_list = [x.strip() for x in line.split("=")[1].split(",")]
        elif line.startswith("; filament_type"):
            material_list = [x.strip() for x in line.split("=")[1].split(",")]

    results = []
    for grams_str, hex_val, material in zip(grams_list, hex_list, material_list):
        grams = float(grams_str)
        if grams == 0.0:
            continue
        if not hex_val.startswith("#"):
            hex_val = "#" + hex_val
        results.append(
            {
                "grams": grams,
                "hex": hex_val,
                "material": material,
            }
        )

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
