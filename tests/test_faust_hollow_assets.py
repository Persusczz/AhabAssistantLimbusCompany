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
    assert any("hollow_awakening.png" in missing for missing in missing_faust_hollow_images())
    with pytest.raises(cannotOperateGameError, match="hollow_awakening.png"):
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


def test_video_resolution_cannot_be_passed_off_as_real_game_template(tmp_path):
    path = tmp_path / "video.png"
    Image.new("RGB", (1536, 864), "white").save(path)
    with pytest.raises(ValueError, match="2560"):
        preparer.prepare_image(path, "hollow_awakening", (0, 0, 100, 100))


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
