from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "manual_test_images"
IMAGE_SIZE = (320, 240)


def load_font(size: int = 28) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw_centered_text(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.ImageFont) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    x = (IMAGE_SIZE[0] - width) // 2
    draw.text((x, y), text, fill=(20, 24, 32), font=font)


def create_target_image(index: int, font: ImageFont.ImageFont) -> Path:
    image = Image.new("RGB", IMAGE_SIZE, color=(248, 250, 252))
    draw = ImageDraw.Draw(image)
    draw.ellipse((95, 45, 225, 175), fill=(220, 38, 38), outline=(127, 29, 29), width=4)
    name = f"target_{index:03d}"
    draw_centered_text(draw, name, 190, font)
    path = OUTPUT_DIR / f"{name}.jpg"
    image.save(path, format="JPEG", quality=92)
    return path


def create_other_image(index: int, font: ImageFont.ImageFont) -> Path:
    image = Image.new("RGB", IMAGE_SIZE, color=(248, 250, 252))
    draw = ImageDraw.Draw(image)
    draw.rectangle((95, 45, 225, 175), fill=(37, 99, 235), outline=(30, 64, 175), width=4)
    name = f"other_{index:03d}"
    draw_centered_text(draw, name, 190, font)
    path = OUTPUT_DIR / f"{name}.jpg"
    image.save(path, format="JPEG", quality=92)
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    font = load_font()
    paths = []
    for index in range(1, 11):
        paths.append(create_target_image(index, font))
    for index in range(1, 11):
        paths.append(create_other_image(index, font))

    print(f"Created {len(paths)} images in {OUTPUT_DIR}")
    for path in paths:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
