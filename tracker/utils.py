import re
from io import BytesIO

import qrcode
from PIL import Image, ImageDraw, ImageFont

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


def rank_spools_by_material_and_color(slicer_hex, slicer_material, spools):
    """Prefer spools matching the slicer's filament type (e.g. don't default a plain
    PLA print to a Black HT-PLA spool just because it's closer alphabetically); fall
    back to plain PLA, then to any material, ranking by color distance within
    whichever group is used."""
    spools = list(spools)
    if slicer_material:
        material_matches = [s for s in spools if s.material.strip().lower() == slicer_material.strip().lower()]
        if material_matches:
            spools = material_matches
        else:
            pla_matches = [s for s in spools if s.material.strip().lower() == "pla"]
            if pla_matches:
                spools = pla_matches
    return rank_spools_by_color(slicer_hex, spools) if slicer_hex else spools


_LABEL_WIDTH = 500
_LABEL_MARGIN = 24


def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_spool_label_png(spool):
    """Render a single downloadable label (QR code + SKU + identifying text) for one
    physical spool, sized for a small Bluetooth label printer or home printer."""
    qr_img = qrcode.make(spool.sku, box_size=10, border=2).convert("RGB")
    qr_size = _LABEL_WIDTH - 2 * _LABEL_MARGIN
    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)

    sku_font = ImageFont.load_default(size=34)
    detail_font = ImageFont.load_default(size=22)

    scratch = Image.new("RGB", (10, 10), "white")
    scratch_draw = ImageDraw.Draw(scratch)
    max_text_width = _LABEL_WIDTH - 2 * _LABEL_MARGIN

    sku_lines = _wrap_text(scratch_draw, spool.sku, sku_font, max_text_width)
    detail_text = f"{spool.brand} {spool.color_name} ({spool.material})".strip()
    detail_lines = _wrap_text(scratch_draw, detail_text, detail_font, max_text_width)

    line_gap = 6
    sku_line_h = sku_font.size + 8
    detail_line_h = detail_font.size + 6
    text_block_h = (len(sku_lines) * sku_line_h) + line_gap + (len(detail_lines) * detail_line_h)

    total_h = _LABEL_MARGIN + qr_size + 18 + text_block_h + _LABEL_MARGIN
    label = Image.new("RGB", (_LABEL_WIDTH, int(total_h)), "white")
    label.paste(qr_img, (_LABEL_MARGIN, _LABEL_MARGIN))

    draw = ImageDraw.Draw(label)
    y = _LABEL_MARGIN + qr_size + 18
    for line in sku_lines:
        w = draw.textlength(line, font=sku_font)
        draw.text(((_LABEL_WIDTH - w) / 2, y), line, font=sku_font, fill="black")
        y += sku_line_h
    y += line_gap
    for line in detail_lines:
        w = draw.textlength(line, font=detail_font)
        draw.text(((_LABEL_WIDTH - w) / 2, y), line, font=detail_font, fill="#444444")
        y += detail_line_h

    buf = BytesIO()
    label.save(buf, format="PNG")
    return buf.getvalue()
