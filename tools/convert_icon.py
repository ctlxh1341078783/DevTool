"""生成 DevTool 应用图标（多尺寸 ICO）"""
from PIL import Image, ImageDraw
import os

SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

def main():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    os.makedirs(out_dir, exist_ok=True)
    ico_path = os.path.join(out_dir, "app_icon.ico")

    print("生成 DevTool 图标...")
    base_size = 256
    img = Image.new("RGBA", (base_size, base_size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = max(1, base_size // 10)
    d.rounded_rectangle(
        [margin, margin, base_size - margin, base_size - margin],
        radius=base_size // 5,
        fill=(78, 110, 242),
    )

    cx, cy = base_size // 2, base_size // 2
    arrow_sz = base_size // 3
    pts = [
        (cx, cy - arrow_sz),
        (cx + arrow_sz, cy + arrow_sz // 2),
        (cx + arrow_sz // 3, cy + arrow_sz // 2),
        (cx + arrow_sz // 3, cy + arrow_sz),
        (cx - arrow_sz // 3, cy + arrow_sz),
        (cx - arrow_sz // 3, cy + arrow_sz // 2),
        (cx - arrow_sz, cy + arrow_sz // 2),
    ]
    d.polygon(pts, fill="white")

    img.save(ico_path, format="ICO", sizes=SIZES)
    size_kb = os.path.getsize(ico_path) / 1024
    print(f"已保存: {ico_path} ({size_kb:.0f} KB)")

if __name__ == "__main__":
    main()
