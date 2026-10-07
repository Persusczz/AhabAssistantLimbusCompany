"""从真实的 2560×1440 游戏截图裁切空洞预设识别模板；不会启动或操作游戏。"""

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from module.config.faust_hollow_assets import FAUST_HOLLOW_IMAGE_DIR, FAUST_HOLLOW_IMAGES


def prepare_image(source: Path, name: str, box: tuple[int, int, int, int]) -> Path:
    if name not in FAUST_HOLLOW_IMAGES:
        raise ValueError(f"未知模板名称：{name}")
    with Image.open(source) as screenshot:
        if screenshot.size != (2560, 1440):
            raise ValueError("需要游戏客户区原始 2560×1440 截图；不能使用网页播放器截图或放大后的视频画面")
        left, top, right, bottom = box
        if not (0 <= left < right <= 2560 and 0 <= top < bottom <= 1440):
            raise ValueError("裁切区域必须在游戏截图内且有非零面积")
        # 识别器忽略 alpha；先把透明像素合成到黑底，避免隐藏的 RGB 像素进入匹配。
        rgba = screenshot.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        image = Image.alpha_composite(background, rgba).convert("RGB").crop(box)
    minimum, maximum = image.convert("L").getextrema()
    if minimum == maximum:
        raise ValueError("选区缺少灰度细节，不能用作识别模板")
    target = FAUST_HOLLOW_IMAGE_DIR / f"{name}.png"
    if target.exists():
        raise FileExistsError(f"模板已存在，请先检查是否需要替换：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--name", choices=FAUST_HOLLOW_IMAGES, required=True)
    parser.add_argument("--box", type=int, nargs=4, required=True, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    args = parser.parse_args()
    print(prepare_image(args.source, args.name, tuple(args.box)))


if __name__ == "__main__":
    main()
