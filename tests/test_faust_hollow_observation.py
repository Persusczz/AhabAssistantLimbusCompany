import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from module.my_error.my_error import cannotOperateGameError


def observation_screen(preset="faust_hollow", missing=None):
    source = Path(__file__).resolve().parents[1] / "tasks/mirror/mirror.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    mirror = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Mirror")
    function = next(node for node in mirror.body if isinstance(node, ast.FunctionDef)
                    and node.name == "select_observe_ego_gift")

    class Screen:
        def __init__(self):
            self.clicks = []

        def find_element(self, path, **kwargs):
            if "observe_burn" in path:
                return None if missing == "anchor" else (100, 100)
            if "observe_bleed" in path:
                return None
            if "Level_III" in path:
                return None if missing == "level" else (300, 240)
            return None

        def mouse_click(self, *point):
            self.clicks.append(point)

        def mouse_drag(self, *args, **kwargs):
            pass

        def find_language_text(self, zh, en, crop):
            return zh == "选择" and missing != "confirmation"

        def click_element(self, path, **kwargs):
            return path.endswith("leave_shop_confirm_assets.png")

    screen = Screen()
    namespace = {
        "auto": screen, "cfg": SimpleNamespace(set_win_size=1440), "re": re,
        "ImageUtils": SimpleNamespace(load_image=lambda path: path,
                                      get_bbox=lambda path: (200, 300, 2000, 1200)),
        "sleep": lambda *args: None, "observe_system": {},
        "log": SimpleNamespace(debug=lambda *args: None, warning=lambda *args: None),
        "cannotOperateGameError": cannotOperateGameError,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    setting = SimpleNamespace(mirror_preset=preset,
                              observe_ego_gift_selected=["general_3_1_7", "general_3_3_3"])
    return lambda: namespace["select_observe_ego_gift"](setting), screen


def test_confirmed_tier_three_rows_are_clicked_before_confirmation():
    select, screen = observation_screen()
    select()
    assert (1290, 320) in screen.clicks
    assert (630, 640) in screen.clicks
    assert screen.clicks.index((1290, 320)) < screen.clicks.index((630, 640))


@pytest.mark.parametrize("missing", ["anchor", "level", "confirmation"])
def test_preset_cannot_continue_after_missing_observation_ui(missing):
    select, screen = observation_screen(missing=missing)
    with pytest.raises(cannotOperateGameError, match="观测"):
        select()
    if missing in ("anchor", "level"):
        assert (1290, 320) not in screen.clicks


def test_standard_observation_still_returns_when_anchor_is_missing():
    select, screen = observation_screen(preset="standard", missing="anchor")
    assert select() is None
    assert screen.clicks == []
