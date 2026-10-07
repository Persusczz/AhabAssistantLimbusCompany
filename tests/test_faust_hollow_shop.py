import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from module.my_error.my_error import cannotOperateGameError


def shop_buyer(preset, aggressive=True):
    source = Path(__file__).resolve().parents[1] / "tasks/mirror/in_shop.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    shop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Shop")
    function = next(node for node in shop.body if isinstance(node, ast.FunctionDef) and node.name == "buy_gifts")

    class Screen:
        def __init__(self):
            self.scanned = []
            self.bought = []

        def take_screenshot(self):
            return object()

        def click_element(self, path, **kwargs):
            self.scanned.append(path)
            if path.endswith(("level_IV_to_buy.png", "level_III_to_buy.png")):
                if path not in self.bought:
                    self.bought.append(path)
                    return True
                return False
            return path.endswith("purchase_assets.png")

        def find_element(self, path, **kwargs):
            self.scanned.append(path)
            return []

        def mouse_click_blank(self, **kwargs):
            pass

    screen = Screen()
    namespace = {
        "auto": screen, "cfg": SimpleNamespace(set_win_size=1440),
        "log": SimpleNamespace(debug=lambda *args: None, warning=lambda *args: None),
        "sleep": lambda *args: None, "retry": lambda: True, "must_purchase": [],
        "cannotOperateGameError": cannotOperateGameError,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    setting = SimpleNamespace(
        mirror_preset=preset, system="poise", shopping_strategy=False, shopping_strategy_select=0,
        fuse_aggressive_switch=aggressive, second_system=False, skill_replacement=False,
        max_keyword_refresh=0, max_normal_refresh=0, _get_cost=lambda: 0,
    )
    return lambda floor: namespace["buy_gifts"](setting, layer=floor), screen


@pytest.mark.parametrize("floor", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("aggressive", [True, False])
def test_preset_buys_tier_three_only_from_second_floor_even_after_fusion(floor, aggressive):
    buy, screen = shop_buyer("faust_hollow", aggressive)
    buy(floor)
    ranks = [Path(path).stem for path in screen.bought]
    assert ranks == ([] if floor == 1 else ["level_III_to_buy"])
    assert "mirror/shop/enhance_gifts/shop_poise.png" in screen.scanned
    assert "mirror/shop/level_IV_to_buy.png" not in screen.scanned


def test_standard_aggressive_shop_keeps_both_material_ranks():
    buy, screen = shop_buyer("standard")
    buy(1)
    assert [Path(path).stem for path in screen.bought] == ["level_IV_to_buy", "level_III_to_buy"]


def test_preset_does_not_buy_when_floor_is_unknown():
    buy, screen = shop_buyer("faust_hollow")
    with pytest.raises(cannotOperateGameError, match="楼层"):
        buy(0)
    assert screen.scanned == []
