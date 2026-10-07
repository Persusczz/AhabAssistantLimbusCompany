import importlib.util
from pathlib import Path

import pytest
from PIL import Image

from module.config.faust_hollow_assets import missing_faust_hollow_images
from module.config.mirror_presets import apply_faust_hollow_preset, ensure_mirror_preset_ready
from module.config.config_typing import TeamSetting
from module.my_error.my_error import cannotOperateGameError


source = Path(__file__).resolve().parents[1] / "scripts/prepare_faust_hollow_image.py"
spec = importlib.util.spec_from_file_location("prepare_faust_hollow_image", source)
preparer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparer)


def test_preflight_lists_missing_images_without_enabling_draft():
    assert any("ryoshu_guard.png" in missing for missing in missing_faust_hollow_images())
    with pytest.raises(cannotOperateGameError, match="ryoshu_guard.png"):
        ensure_mirror_preset_ready(apply_faust_hollow_preset(TeamSetting()))


def test_crop_preserves_original_pixels_and_flattens_alpha_on_black(tmp_path, monkeypatch):
    screenshot = Image.new("RGBA", (2560, 1440), (255, 255, 255, 0))
    screenshot.putpixel((10, 10), (100, 150, 200, 255))
    path = tmp_path / "game.png"
    screenshot.save(path)
    monkeypatch.setattr(preparer, "FAUST_HOLLOW_IMAGE_DIR", tmp_path / "templates")
    target = preparer.prepare_image(path, "hollow_awakening", (9, 9, 12, 12))
    with Image.open(target) as result:
        assert result.mode == "RGB"
        assert result.size == (3, 3)
        assert result.getpixel((0, 0)) == (0, 0, 0)
        assert result.getpixel((1, 1)) == (100, 150, 200)
    with pytest.raises(FileExistsError):
        preparer.prepare_image(path, "hollow_awakening", (9, 9, 12, 12))


def test_nonstandard_resolution_requires_explicit_calibration(tmp_path):
    path = tmp_path / "video.png"
    Image.new("RGB", (1536, 864), "white").save(path)
    with pytest.raises(ValueError, match="2560"):
        preparer.prepare_image(path, "hollow_awakening", (0, 0, 100, 100))


def test_cropped_game_image_is_scaled_to_baseline_with_explicit_calibration(tmp_path, monkeypatch):
    import cv2
    import numpy as np

    pixels = np.random.default_rng(0).integers(0, 256, size=(90, 120, 3), dtype=np.uint8)
    path = tmp_path / "crop.png"
    Image.fromarray(pixels).save(path)
    monkeypatch.setattr(preparer, "FAUST_HOLLOW_IMAGE_DIR", tmp_path / "templates")
    target = preparer.prepare_image(path, "hollow_awakening", (0, 0, 120, 90), source_scale=0.75)
    result = np.array(Image.open(target))
    assert result.shape == (120, 160, 3)
    assert np.array_equal(result, cv2.resize(pixels, (160, 120), interpolation=cv2.INTER_LINEAR))


@pytest.mark.parametrize("scale", [0, -1, float("nan"), float("inf")])
def test_invalid_calibration_does_not_create_resource(tmp_path, monkeypatch, scale):
    path = tmp_path / "crop.png"
    Image.new("RGB", (120, 90), "white").save(path)
    monkeypatch.setattr(preparer, "FAUST_HOLLOW_IMAGE_DIR", tmp_path / "templates")
    with pytest.raises(ValueError, match="有限正数"):
        preparer.prepare_image(path, "hollow_awakening", (0, 0, 120, 90), scale)
    assert not (tmp_path / "templates").exists()


@pytest.mark.parametrize("box", [(-1, 0, 10, 10), (0, 0, 2600, 10), (10, 10, 10, 20)])
def test_invalid_crop_does_not_create_resource(tmp_path, monkeypatch, box):
    path = tmp_path / "game.png"
    Image.new("RGB", (2560, 1440), "white").save(path)
    monkeypatch.setattr(preparer, "FAUST_HOLLOW_IMAGE_DIR", tmp_path / "templates")
    with pytest.raises(ValueError):
        preparer.prepare_image(path, "hollow_awakening", box)
    assert not (tmp_path / "templates").exists()


@pytest.mark.parametrize("color", ["black", "white", "red"])
def test_constant_color_cannot_become_false_positive_template(tmp_path, monkeypatch, color):
    path = tmp_path / "game.png"
    Image.new("RGB", (2560, 1440), color).save(path)
    monkeypatch.setattr(preparer, "FAUST_HOLLOW_IMAGE_DIR", tmp_path / "templates")
    with pytest.raises(ValueError, match="细节"):
        preparer.prepare_image(path, "hollow_awakening", (0, 0, 100, 100))


@pytest.mark.parametrize("window_height", [1080, 1440])
def test_real_overclock_marker_matches_native_ui_and_does_not_match_gold_or_blue_glow(monkeypatch, window_height):
    import cv2
    import numpy as np
    from types import SimpleNamespace
    import utils.image_utils as image_utils

    monkeypatch.setattr(image_utils, "cfg", SimpleNamespace(set_win_size=window_height))
    root = Path(__file__).resolve().parents[1]
    directory = root / "assets/images/default/share/battle/faust_hollow"
    rgb = np.array(Image.open(directory / "hollow_overclock_selected.png"))
    marker = image_utils.ImageUtils._prepare_loaded_image(rgb, resize=True)
    original = np.array(Image.open(root / "tests/fixtures/faust_hollow/overclock_slot_1080.png"))
    ratio = window_height / 1080
    screenshot = cv2.resize(original, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_LINEAR)
    grey = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
    _, score, _, position = cv2.minMaxLoc(cv2.matchTemplate(grey, marker, cv2.TM_CCOEFF_NORMED))
    assert score >= 0.9
    assert abs(position[0] - 24 * ratio) <= 1
    assert abs(position[1] - 82 * ratio) <= 1

    for name in ("hollow_skill_gold", "hollow_skill_blue"):
        rgb = np.array(Image.open(directory / f"{name}.png"))
        icon = image_utils.ImageUtils._prepare_loaded_image(rgb, resize=True)
        negative = np.zeros((300, 300), dtype=np.uint8)
        negative[20:20 + icon.shape[0], 20:20 + icon.shape[1]] = icon
        assert cv2.minMaxLoc(cv2.matchTemplate(negative, marker, cv2.TM_CCOEFF_NORMED))[1] < 0.9
