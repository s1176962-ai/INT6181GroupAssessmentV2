"""Generate flat educational illustrations for every question (Pillow)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "images" / "questions"
BANK = ROOT / "data" / "questions"

BG = (244, 241, 234)
SURFACE = (255, 252, 247)
PRIMARY = (31, 122, 76)
INK = (28, 28, 30)
MUTED = (92, 92, 87)
ACCENT = (58, 90, 124)
WARM = (196, 120, 60)
RED = (194, 74, 74)
SKY = (180, 210, 230)
LEAF = (90, 160, 100)
W, H = 480, 270


def font(size: int):
    for name in ("seguiemj.ttf", "segoeui.ttf", "arial.ttf", "msyh.ttc"):
        path = Path(r"C:\Windows\Fonts") / name
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def canvas():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (16, 16, W - 16, H - 16), radius=24, fill=SURFACE, outline=(228, 223, 212), width=2
    )
    return img, draw


def save(img: Image.Image, qid: str) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    rel = f"assets/images/questions/{qid}.png"
    img.save(ROOT / rel, "PNG")
    return rel


def label(draw, text, y=H - 48):
    draw.text((W / 2, y), text, fill=MUTED, font=font(16), anchor="mm")


def draw_apple(draw):
    draw.ellipse((175, 85, 255, 185), fill=(210, 55, 55), outline=INK, width=2)
    draw.ellipse((225, 85, 305, 185), fill=(230, 75, 70), outline=INK, width=2)
    draw.ellipse((215, 75, 265, 110), fill=SURFACE)
    draw.line((240, 78, 252, 42), fill=(110, 70, 35), width=5)
    draw.ellipse((248, 35, 295, 72), fill=LEAF, outline=PRIMARY, width=2)
    draw.ellipse((205, 115, 225, 135), fill=(255, 200, 180))


def draw_sun_snow(draw):
    draw.ellipse((90, 70, 170, 150), fill=(240, 190, 70), outline=WARM, width=2)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        draw.line(
            (
                130 + 50 * math.cos(rad),
                110 + 50 * math.sin(rad),
                130 + 70 * math.cos(rad),
                110 + 70 * math.sin(rad),
            ),
            fill=WARM,
            width=3,
        )
    draw.ellipse((300, 90, 380, 170), fill=(230, 240, 255), outline=ACCENT, width=2)
    draw.polygon([(340, 100), (355, 130), (325, 130)], fill=SKY)


def draw_book(draw):
    draw.rounded_rectangle(
        (150, 70, 330, 200), radius=8, fill=(250, 245, 235), outline=PRIMARY, width=2
    )
    draw.line((240, 70, 240, 200), fill=PRIMARY, width=3)
    for y in (100, 130, 160):
        draw.line((160, y, 225, y), fill=MUTED, width=2)
        draw.line((255, y, 320, y), fill=MUTED, width=2)


def draw_children(draw):
    for x, fill in ((160, PRIMARY), (280, ACCENT)):
        draw.ellipse((x, 70, x + 50, 120), fill=fill)
        draw.rounded_rectangle((x - 5, 115, x + 55, 200), radius=12, fill=fill)


def draw_mountain(draw):
    draw.polygon([(80, 200), (180, 70), (280, 200)], fill=ACCENT)
    draw.polygon([(200, 200), (300, 90), (400, 200)], fill=PRIMARY)
    draw.polygon([(180, 70), (200, 95), (160, 95)], fill=SURFACE)


def draw_smile(draw):
    draw.ellipse((180, 60, 300, 180), fill=(255, 220, 120), outline=WARM, width=3)
    draw.ellipse((210, 100, 230, 120), fill=INK)
    draw.ellipse((250, 100, 270, 120), fill=INK)
    draw.arc((210, 110, 270, 160), 20, 160, fill=INK, width=4)


def draw_palette(draw):
    colors = [(220, 70, 70), (70, 140, 220), (90, 180, 90), (240, 190, 70)]
    for i, c in enumerate(colors):
        x = 120 + i * 60
        draw.ellipse((x, 100, x + 50, 150), fill=c, outline=INK, width=2)


def draw_runner(draw):
    draw.ellipse((220, 55, 260, 95), fill=PRIMARY)
    draw.line((240, 95, 240, 150), fill=PRIMARY, width=6)
    draw.line((240, 110, 200, 140), fill=PRIMARY, width=5)
    draw.line((240, 110, 285, 130), fill=PRIMARY, width=5)
    draw.line((240, 150, 210, 200), fill=PRIMARY, width=5)
    draw.line((240, 150, 275, 200), fill=PRIMARY, width=5)


def draw_gift(draw):
    draw.rounded_rectangle((180, 110, 300, 200), radius=8, fill=RED, outline=INK, width=2)
    draw.rectangle((230, 110, 250, 200), fill=WARM)
    draw.rectangle((180, 145, 300, 165), fill=WARM)
    draw.ellipse((220, 85, 260, 115), fill=LEAF)


def draw_am(draw):
    draw.rounded_rectangle(
        (140, 80, 340, 180), radius=16, fill=(230, 245, 235), outline=PRIMARY, width=3
    )
    draw.text((W / 2, 130), "I am", fill=PRIMARY, font=font(36), anchor="mm")


def draw_playing(draw):
    draw.ellipse((150, 70, 200, 120), fill=ACCENT)
    draw.ellipse((280, 70, 330, 120), fill=PRIMARY)
    draw.rounded_rectangle((145, 120, 205, 200), radius=10, fill=ACCENT)
    draw.rounded_rectangle((275, 120, 335, 200), radius=10, fill=PRIMARY)
    draw.ellipse((230, 150, 250, 170), fill=WARM)


def draw_arrow_past(draw):
    draw.ellipse((100, 100, 160, 160), fill=MUTED)
    draw.polygon([(200, 90), (320, 130), (200, 170)], fill=PRIMARY)
    draw.text((130, 130), "go", fill=SURFACE, font=font(18), anchor="mm")
    draw.text((250, 130), "went", fill=SURFACE, font=font(18), anchor="mm")


def draw_umbrella(draw):
    draw.pieslice((160, 70, 320, 180), 180, 360, fill=ACCENT, outline=INK, width=2)
    draw.line((240, 125, 240, 210), fill=INK, width=4)
    draw.arc((230, 200, 270, 230), 0, 180, fill=INK, width=3)


def draw_ifthen(draw):
    draw.rounded_rectangle(
        (70, 90, 210, 170), radius=12, fill=(235, 245, 255), outline=ACCENT, width=2
    )
    draw.rounded_rectangle(
        (270, 90, 410, 170), radius=12, fill=(235, 245, 235), outline=PRIMARY, width=2
    )
    draw.polygon([(220, 120), (260, 130), (220, 140)], fill=MUTED)
    draw.text((140, 130), "If…", fill=ACCENT, font=font(22), anchor="mm")
    draw.text((340, 130), "then…", fill=PRIMARY, font=font(22), anchor="mm")


def draw_passive(draw):
    draw.rounded_rectangle((90, 90, 220, 170), radius=10, fill=SURFACE, outline=MUTED, width=2)
    draw.rounded_rectangle(
        (260, 90, 390, 170), radius=10, fill=(230, 245, 235), outline=PRIMARY, width=3
    )
    draw.text((155, 130), "active", fill=MUTED, font=font(18), anchor="mm")
    draw.text((325, 130), "passive", fill=PRIMARY, font=font(18), anchor="mm")


def draw_pets(draw):
    # two cats + dog
    for x in (120, 200):
        draw.ellipse((x, 110, x + 50, 160), fill=(240, 180, 100))
        draw.polygon([(x + 8, 120), (x + 5, 95), (x + 22, 110)], fill=(240, 180, 100))
        draw.polygon([(x + 42, 120), (x + 45, 95), (x + 28, 110)], fill=(240, 180, 100))
    draw.ellipse((300, 115, 370, 175), fill=(180, 140, 100))
    draw.ellipse((350, 100, 385, 135), fill=(180, 140, 100))


def draw_alarm(draw):
    draw.ellipse((190, 80, 290, 180), fill=SURFACE, outline=RED, width=4)
    draw.line((240, 100, 240, 130), fill=INK, width=4)
    draw.line((240, 130, 265, 145), fill=INK, width=4)
    draw.arc((175, 70, 205, 100), 200, 340, fill=RED, width=4)
    draw.arc((275, 70, 305, 100), 200, 340, fill=RED, width=4)


def draw_reluctant(draw):
    draw.ellipse((190, 70, 290, 170), fill=(220, 225, 230), outline=MUTED, width=3)
    draw.ellipse((215, 105, 230, 120), fill=INK)
    draw.ellipse((250, 105, 265, 120), fill=INK)
    draw.arc((215, 135, 265, 160), 200, 340, fill=INK, width=3)


def draw_better(draw):
    draw.text((W / 2, 120), "good → better", fill=PRIMARY, font=font(28), anchor="mm")
    draw.polygon([(340, 120), (370, 110), (370, 130)], fill=PRIMARY)


def draw_neither(draw):
    draw.rounded_rectangle((100, 90, 210, 170), radius=10, fill=SURFACE, outline=MUTED, width=2)
    draw.rounded_rectangle((270, 90, 380, 170), radius=10, fill=SURFACE, outline=MUTED, width=2)
    draw.line((120, 100, 190, 160), fill=RED, width=3)
    draw.line((120, 160, 190, 100), fill=RED, width=3)
    draw.line((290, 100, 360, 160), fill=RED, width=3)
    draw.line((290, 160, 360, 100), fill=RED, width=3)
    draw.text((W / 2, 200), "neither", fill=MUTED, font=font(18), anchor="mm")


def draw_math_expr(draw, text):
    draw.rounded_rectangle(
        (80, 85, 400, 175), radius=18, fill=(235, 245, 238), outline=PRIMARY, width=3
    )
    draw.text((W / 2, 130), text, fill=PRIMARY, font=font(34), anchor="mm")


def draw_circle(draw):
    draw.ellipse((165, 55, 315, 205), outline=PRIMARY, width=6)


def draw_square(draw):
    draw.rounded_rectangle((165, 60, 315, 210), radius=8, outline=PRIMARY, width=6)


def draw_fraction(draw, top, bottom):
    draw.text((W / 2, 100), str(top), fill=PRIMARY, font=font(36), anchor="mm")
    draw.line((200, 130, 280, 130), fill=PRIMARY, width=4)
    draw.text((W / 2, 160), str(bottom), fill=PRIMARY, font=font(36), anchor="mm")


def draw_pie_half_quarter(draw):
    draw.pieslice((90, 60, 230, 200), 270, 90, fill=PRIMARY)
    draw.ellipse((90, 60, 230, 200), outline=INK, width=2)
    draw.pieslice((260, 60, 400, 200), 270, 0, fill=ACCENT)
    draw.ellipse((260, 60, 400, 200), outline=INK, width=2)


def draw_algebra(draw, text):
    draw_math_expr(draw, text)


def draw_percent(draw, text):
    draw.ellipse((90, 70, 190, 170), fill=(230, 245, 235), outline=PRIMARY, width=3)
    draw.text((140, 120), "%", fill=PRIMARY, font=font(36), anchor="mm")
    draw.text((300, 120), text, fill=INK, font=font(24), anchor="mm")


def draw_bars(draw):
    heights = [60, 100, 140, 180]
    for i, h in enumerate(heights):
        x = 120 + i * 60
        draw.rounded_rectangle(
            (x, 210 - h, x + 40, 210), radius=6, fill=PRIMARY if i % 2 == 0 else ACCENT
        )


def draw_die(draw):
    draw.rounded_rectangle((180, 70, 300, 190), radius=16, fill=SURFACE, outline=INK, width=3)
    spots = [(210, 100), (270, 100), (240, 130), (210, 160), (270, 160)]
    for x, y in spots:
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=INK)


def draw_roots(draw):
    draw.ellipse((185, 35, 295, 100), fill=LEAF, outline=PRIMARY, width=2)
    draw.ellipse((160, 55, 220, 105), fill=(110, 170, 105))
    draw.ellipse((260, 55, 320, 105), fill=(110, 170, 105))
    draw.line((240, 95, 240, 145), fill=(90, 140, 80), width=10)
    draw.rectangle((40, 145, 440, 230), fill=(214, 196, 160))
    for dx, dy in ((-55, 55), (-25, 60), (0, 65), (30, 58), (60, 50)):
        draw.line((240, 145, 240 + dx, 145 + dy), fill=(130, 90, 50), width=4)
        draw.line((240 + dx, 145 + dy, 240 + dx - 12, 145 + dy + 18), fill=(150, 110, 70), width=3)


def draw_mars(draw):
    draw.ellipse((160, 50, 320, 210), fill=(186, 72, 48), outline=(120, 40, 30), width=3)
    draw.ellipse((190, 85, 230, 120), fill=(160, 55, 40))
    draw.ellipse((250, 130, 295, 165), fill=(150, 50, 38))
    draw.arc((175, 70, 255, 120), 10, 200, fill=(140, 45, 35), width=5)
    draw.ellipse((200, 55, 230, 75), fill=(230, 200, 180))
    draw.ellipse((100, 70, 130, 100), fill=(200, 200, 210))
    draw.ellipse((350, 150, 375, 175), fill=(180, 180, 190))


def draw_copper(draw):
    draw.rounded_rectangle(
        (150, 100, 330, 150), radius=8, fill=(200, 120, 60), outline=INK, width=2
    )
    draw.ellipse((140, 95, 170, 155), fill=(220, 150, 80), outline=INK, width=2)
    draw.ellipse((310, 95, 340, 155), fill=(220, 150, 80), outline=INK, width=2)
    for x in range(180, 310, 25):
        draw.arc((x, 115, x + 20, 135), 0, 180, fill=(255, 220, 120), width=2)


def draw_ice(draw):
    draw.rounded_rectangle(
        (170, 90, 310, 190), radius=12, fill=(210, 235, 250), outline=ACCENT, width=3
    )
    draw.polygon([(190, 110), (210, 150), (170, 150)], fill=SURFACE)


def draw_co2(draw):
    draw.ellipse((200, 70, 280, 150), fill=LEAF)
    draw.line((240, 150, 240, 200), fill=(120, 80, 40), width=5)
    draw.ellipse((160, 50, 200, 90), fill=SKY, outline=ACCENT, width=2)
    draw.text((180, 70), "CO₂", fill=ACCENT, font=font(12), anchor="mm")


def draw_heart(draw):
    draw.ellipse((175, 75, 245, 145), fill=(210, 55, 70), outline=(150, 30, 45), width=2)
    draw.ellipse((235, 75, 305, 145), fill=(230, 70, 85), outline=(150, 30, 45), width=2)
    draw.polygon([(178, 120), (240, 205), (302, 120)], fill=(220, 60, 75))
    draw.ellipse((200, 95, 220, 115), fill=(255, 180, 190))


def draw_cell(draw):
    draw.ellipse((160, 60, 320, 210), fill=(230, 245, 235), outline=PRIMARY, width=4)
    draw.ellipse((210, 105, 270, 165), fill=PRIMARY)


def draw_leaves(draw):
    for x in (150, 220, 290):
        draw.ellipse((x, 100, x + 50, 160), fill=LEAF, outline=PRIMARY, width=2)
        draw.line((x + 25, 160, x + 25, 200), fill=(120, 80, 40), width=3)


def draw_nucleus(draw):
    draw.ellipse((160, 60, 320, 210), outline=PRIMARY, width=3)
    draw.ellipse((210, 105, 270, 165), fill=ACCENT)
    draw.text((240, 135), "DNA", fill=SURFACE, font=font(14), anchor="mm")


def draw_gravity(draw):
    draw.ellipse((200, 50, 280, 110), fill=ACCENT)
    draw.polygon([(240, 120), (255, 160), (225, 160)], fill=PRIMARY)
    draw.ellipse((225, 175, 255, 205), fill=WARM)


def draw_newton(draw):
    draw.rounded_rectangle(
        (140, 90, 340, 170), radius=14, fill=(235, 245, 255), outline=ACCENT, width=3
    )
    draw.text((W / 2, 130), "1 N = 1 kg·m/s²", fill=ACCENT, font=font(22), anchor="mm")


def draw_light_sound(draw):
    draw.ellipse((120, 100, 180, 160), fill=(255, 220, 80))
    for i in range(3):
        r = 40 + i * 18
        draw.arc((240 - r, 130 - r, 240 + r, 130 + r), -40, 40, fill=ACCENT, width=3)
    draw.text((150, 190), "light", fill=MUTED, font=font(14), anchor="mm")
    draw.text((300, 190), "sound", fill=MUTED, font=font(14), anchor="mm")


def draw_force(draw):
    draw.rounded_rectangle((180, 110, 260, 170), radius=8, fill=MUTED)
    draw.polygon([(270, 110), (340, 140), (270, 170)], fill=PRIMARY)
    draw.text((W / 2, 200), "F = ma", fill=PRIMARY, font=font(20), anchor="mm")


def draw_steam(draw):
    draw.ellipse((180, 140, 300, 210), fill=ACCENT)
    for x in (200, 230, 260):
        draw.arc((x, 70, x + 30, 140), 200, 340, fill=MUTED, width=3)


def draw_element(draw):
    draw.ellipse((190, 70, 290, 170), fill=(235, 245, 255), outline=ACCENT, width=3)
    draw.text((240, 120), "O", fill=ACCENT, font=font(48), anchor="mm")
    draw.text((240, 200), "element", fill=MUTED, font=font(16), anchor="mm")


def draw_atom(draw):
    draw.ellipse((225, 115, 255, 145), fill=RED)
    draw.ellipse((170, 70, 310, 210), outline=ACCENT, width=2)
    draw.ellipse((190, 90, 290, 190), outline=PRIMARY, width=2)
    draw.ellipse((280, 100, 295, 115), fill=ACCENT)


def draw_sun(draw):
    draw.ellipse((170, 60, 310, 200), fill=(255, 200, 70), outline=WARM, width=3)
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        draw.line(
            (
                240 + 80 * math.cos(rad),
                130 + 80 * math.sin(rad),
                240 + 105 * math.cos(rad),
                130 + 105 * math.sin(rad),
            ),
            fill=WARM,
            width=3,
        )


def draw_earth_day(draw):
    draw.ellipse((170, 60, 310, 200), fill=ACCENT, outline=INK, width=2)
    draw.chord((170, 60, 310, 200), 270, 90, fill=(40, 60, 90))
    draw.ellipse((80, 90, 140, 150), fill=(255, 210, 80))


def draw_wind(draw):
    draw.polygon([(140, 180), (180, 80), (200, 180)], fill=MUTED)
    draw.ellipse((200, 70, 250, 120), fill=SKY)
    for y in (100, 130, 160):
        draw.arc((260, y - 20, 380, y + 20), 0, 180, fill=ACCENT, width=3)


def draw_recycle(draw):
    draw.ellipse((170, 60, 310, 200), outline=PRIMARY, width=8)
    draw.polygon([(240, 50), (265, 85), (215, 85)], fill=PRIMARY)
    draw.polygon([(310, 140), (275, 165), (295, 110)], fill=LEAF)
    draw.polygon([(170, 140), (205, 110), (185, 165)], fill=ACCENT)


ART = {
    "ENG001": (draw_apple, "apple"),
    "ENG002": (draw_sun_snow, "hot ↔ cold"),
    "ENG003": (draw_book, "grammar"),
    "ENG004": (draw_children, "child → children"),
    "ENG005": (draw_mountain, "huge"),
    "ENG006": (draw_smile, "happy"),
    "ENG007": (draw_palette, "color"),
    "ENG008": (draw_runner, "quick / fast"),
    "ENG009": (draw_gift, "generous"),
    "ENG010": (draw_am, "I am"),
    "ENG011": (draw_playing, "are playing"),
    "ENG012": (draw_arrow_past, "go → went"),
    "ENG013": (draw_umbrella, "an umbrella"),
    "ENG014": (draw_ifthen, "conditional"),
    "ENG015": (draw_passive, "passive voice"),
    "ENG016": (draw_pets, "pets"),
    "ENG017": (draw_alarm, "woke up late"),
    "ENG018": (draw_reluctant, "reluctant"),
    "ENG019": (draw_better, "good → better"),
    "ENG020": (draw_neither, "neither … is"),
    "MAT001": (lambda d: draw_math_expr(d, "7 + 8"), None),
    "MAT002": (lambda d: draw_math_expr(d, "3 × (4 + 2)"), None),
    "MAT003": (draw_circle, "circle"),
    "MAT004": (draw_square, "square"),
    "MAT005": (draw_pie_half_quarter, "½ + ¼"),
    "MAT006": (lambda d: draw_math_expr(d, "9 × 6"), None),
    "MAT007": (lambda d: draw_math_expr(d, "56 ÷ 7"), None),
    "MAT008": (lambda d: draw_math_expr(d, "5² + 3²"), None),
    "MAT009": (lambda d: draw_math_expr(d, "-4 + 9"), None),
    "MAT010": (lambda d: draw_fraction(d, 1, 2), None),
    "MAT011": (lambda d: draw_math_expr(d, "⅔ × ¾"), None),
    "MAT012": (lambda d: draw_math_expr(d, "¾ ÷ ⅖"), None),
    "MAT013": (lambda d: draw_algebra(d, "x + 5 = 12"), None),
    "MAT014": (lambda d: draw_algebra(d, "3x − 4 = 11"), None),
    "MAT015": (lambda d: draw_algebra(d, "x² = 25"), None),
    "MAT016": (lambda d: draw_percent(d, "10% of 80"), None),
    "MAT017": (lambda d: draw_percent(d, "−15%"), None),
    "MAT018": (draw_bars, "mean"),
    "MAT019": (draw_die, "probability"),
    "MAT020": (lambda d: draw_algebra(d, "(x+2)(x+3)"), None),
    "SCI001": (draw_roots, "roots"),
    "SCI002": (draw_mars, "Mars"),
    "SCI003": (draw_copper, "conductor"),
    "SCI004": (draw_ice, "ice"),
    "SCI005": (draw_co2, "photosynthesis"),
    "SCI006": (draw_heart, "heart"),
    "SCI007": (draw_cell, "cell"),
    "SCI008": (draw_leaves, "plants"),
    "SCI009": (draw_nucleus, "nucleus"),
    "SCI010": (draw_gravity, "gravity"),
    "SCI011": (draw_newton, "newton"),
    "SCI012": (draw_light_sound, "light vs sound"),
    "SCI013": (draw_force, "force"),
    "SCI014": (draw_steam, "evaporation"),
    "SCI015": (draw_element, "element"),
    "SCI016": (draw_atom, "atom"),
    "SCI017": (draw_sun, "the Sun"),
    "SCI018": (draw_earth_day, "day & night"),
    "SCI019": (draw_wind, "renewable"),
    "SCI020": (draw_recycle, "decomposers"),
}


def build(qid: str) -> str:
    img, draw = canvas()
    painter, caption = ART[qid]
    painter(draw)
    if caption:
        label(draw, caption)
    return save(img, qid)


def update_bank() -> None:
    for path in sorted(BANK.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for question in data:
            qid = question["id"]
            if qid not in ART:
                continue
            # Keep existing geometry assets that option images depend on.
            if qid == "MAT003" and question.get("question_image") == "assets/circle.png":
                # Still generate a matching preview art, but leave the bank path
                # pointing at the existing circle used by tests/content.
                build(qid)
                continue
            rel = build(qid)
            if question.get("question_image") != rel:
                question["question_image"] = rel
                changed = True
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("updated", path.name)
        else:
            print("unchanged bank", path.name)


def main() -> None:
    for qid in ART:
        build(qid)
        print("art", qid)
    update_bank()


if __name__ == "__main__":
    main()
