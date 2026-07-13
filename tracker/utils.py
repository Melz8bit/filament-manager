import re

# Ordered most-specific first so "Dark Grey" matches before "Grey"
_MATERIALS = ["PLA-CF", "PETG-CF", "PA-CF", "PLA+", "PETG+", "PETG", "PLA",
               "ABS", "ASA", "TPU", "HIPS", "Nylon", "PC", "PEEK", "PVA"]

_FILAMENT_KEYWORDS = ["filament", "3d print", "1.75mm", "2.85mm", "1.75 mm", "2.85 mm", "3d printer"]

_COLORS = [
    "Dark Grey", "Light Grey", "Dark Gray", "Light Gray",
    "Dark Blue", "Light Blue", "Dark Green", "Light Green",
    "Army Green", "Forest Green", "Army Dark Green",
    "Dark Red", "Dark Brown", "Rose Gold", "Matte Black",
    "Silk Gold", "Silk Silver", "Silk White", "Silk Black",
    "Black", "White", "Grey", "Gray", "Red", "Blue", "Green",
    "Yellow", "Orange", "Purple", "Pink", "Brown", "Beige",
    "Clear", "Natural", "Silver", "Gold", "Bronze", "Copper",
    "Marble", "Rainbow", "Navy", "Teal", "Cyan", "Magenta",
    "Violet", "Indigo", "Cream", "Ivory", "Olive", "Salmon",
    "Coral", "Mint", "Tan", "Transparent", "Translucent", "Silk",
]


def parse_filament_product(title: str, brand: str = "", description: str = "") -> dict:
    """Extract brand, material, color_name, full_weight_g from a product listing."""
    upper = title.upper()

    parsed_brand = brand.title() if brand else (title.split()[0].title() if title else "")

    material = next((m for m in _MATERIALS if m.upper() in upper), "")

    full_weight_g = 0
    m = re.search(r"(\d+(?:\.\d+)?)\s*KG", upper)
    if m:
        full_weight_g = int(float(m.group(1)) * 1000)
    else:
        m = re.search(r"(\d{3,4})\s*G\b", upper)
        if m:
            full_weight_g = int(m.group(1))

    color_name = next((c for c in _COLORS if c.upper() in upper), "")

    return {
        "brand": parsed_brand,
        "material": material,
        "color_name": color_name,
        "full_weight_g": full_weight_g,
    }


def is_filament_product(title: str, description: str = "") -> bool:
    combined = (title + " " + description).upper()
    if any(m.upper() in combined for m in _MATERIALS):
        return True
    return any(k.upper() in combined for k in _FILAMENT_KEYWORDS)


def hex_distance(hex1, hex2) -> float:
    r1 = int(hex1[1:3], 16)
    g1 = int(hex1[3:5], 16)
    b1 = int(hex1[5:7], 16)

    r2 = int(hex2[1:3], 16)
    g2 = int(hex2[3:5], 16)
    b2 = int(hex2[5:7], 16)

    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def rank_spools_by_color(slicer_hex, spools):
    return sorted(spools, key=lambda s: hex_distance(slicer_hex, s.color_hex))
