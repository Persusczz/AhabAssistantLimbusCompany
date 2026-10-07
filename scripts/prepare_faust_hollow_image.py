"""从真实游戏截图裁切识别模板；显式校准比例后统一到 2560×1440 基准。"""

import argparse
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from module.config.faust_hollow_assets import (
    FAUST_HOLLOW_IMAGE_DIR, FAUST_HOLLOW_IMAGES, FAUST_HOLLOW_REFERENCE_IMAGES,
)

IMAGE_NAMES = FAUST_HOLLOW_IMAGES | FAUST_HOLLOW_REFERENCE_IMAGES


def prepare_image(source: Path, name: str, box: tuple[int, int, int, int],
                  source_scale: float | None = None) -> Path:
    if name not in IMAGE_NAMES:
        raise ValueError(f"未知模板名称：{name}")
    with Image.open(source) as screenshot:
        if source_scale is None:
            if screenshot.size != (2560, 1440):
                raise ValueError("非 2560×1440 原图或已裁切图片必须显式提供 source_scale 校准比例")
            source_scale = 1.0
        if not math.isfinite(source_scale) or source_scale <= 0:
            raise ValueError("source_scale 必须为有限正数")
        width, height = screenshot.size
        left, top, right, bottom = box
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError("裁切区域必须在游戏截图内且有非零面积")
        # 识别器忽略 alpha；先把透明像素合成到黑底，避免隐藏的 RGB 像素进入匹配。
        rgba = screenshot.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        image = Image.alpha_composite(background, rgba).convert("RGB").crop(box)
    minimum, maximum = image.convert("L").getextrema()
    if minimum == maximum:
        raise ValueError("选区缺少灰度细节，不能用作识别模板")
    if source_scale != 1:
        # 与 ImageUtils 的 OpenCV 缩放对应；裁片本身的高度不能当作窗口高度。
        pixels = cv2.resize(np.array(image), None, fx=1 / source_scale, fy=1 / source_scale,
                            interpolation=cv2.INTER_LINEAR if source_scale < 1 else cv2.INTER_AREA)
        image = Image.fromarray(pixels)
    target = FAUST_HOLLOW_IMAGE_DIR / f"{name}.png"
    if target.exists():
        raise FileExistsError(f"模板已存在，请先检查是否需要替换：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--name", choices=IMAGE_NAMES, required=True)
    parser.add_argument("--box", type=int, nargs=4, required=True, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--source-scale", type=float,
                        help="原截图 UI 相对 2560×1440 基准的比例，例如经标定的 1920 宽截图为 0.75")
    args = parser.parse_args()
    print(prepare_image(args.source, args.name, tuple(args.box), args.source_scale))


if __name__ == "__main__":
    main()
