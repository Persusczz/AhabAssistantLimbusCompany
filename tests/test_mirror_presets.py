from pathlib import Path

import pytest
from pydantic import ValidationError

from module.config.config_typing import TeamSetting
from module.config.mirror_presets import (
    apply_faust_hollow_preset,
    ensure_mirror_preset_ready,
    load_faust_hollow_plan,
    match_faust_hollow_pack,
)
from module.my_error.my_error import cannotOperateGameError


def test_preset_resets_conflicting_settings_and_preserves_team_and_statistics():
    original = TeamSetting(
        team_number=6,
        use_starlight=True,
        defense_for_solo=True,
        defense_first_round=True,
        ignore_shop=[1] * 5,
        mirror_normal_count=12,
        total_mirror_time_normal=[10, 20, 30],
    )
    preset = apply_faust_hollow_preset(original)
    assert preset.mirror_preset == "faust_hollow"
    assert preset.team_number == 6
    assert preset.mirror_normal_count == 12
    assert preset.total_mirror_time_normal == [10, 20, 30]
    assert preset.team_system == 4
    assert preset.opening_items_system == 4
    assert preset.opening_items_select == 0
    assert preset.opening_bonus == [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]
    assert preset.use_starlight is False
    assert preset.defense_for_solo is False
    assert preset.defense_first_round is False
    assert preset.ignore_shop == [0] * 5
    assert preset.sinner_order == [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert preset.normal_to_hard_floor == 0
    assert original.use_starlight is True
    preset.total_mirror_time_normal[0] = 99
    assert original.total_mirror_time_normal[0] == 10


def test_plan_keeps_unknown_observation_positions_and_gifts_explicit():
    plan = load_faust_hollow_plan()
    assert plan["status"] == "draft"
    assert len(plan["observed_gifts"]) == 2
    assert all(gift["selection"] is None for gift in plan["observed_gifts"])
    assert len(plan["tier_iv_gifts"]) == 4
    assert sum(gift is None for gift in plan["tier_iv_gifts"]) == 2
    assert plan["interceptor"] == "黑派良秀"
    assert plan["floors"][3]["deployed"] == ["浮士德", "黑派良秀"]
    assert plan["floors"][4]["deployed"] == ["浮士德"]


@pytest.mark.parametrize(
    ("floor", "name"),
    [(1, "赌徒"), (2, "地狱鸡"), (3, "情感困惑"), (4, "憎恶与绝望"), (5, "2 号线")],
)
def test_theme_pack_policy_accepts_only_the_requested_floor(floor, name):
    assert match_faust_hollow_pack(floor, name)
    assert not match_faust_hollow_pack(floor, "未知主题包")


@pytest.mark.parametrize("name", ["1号线", "3号线", "4号线", "12号线", "Line 1", "Line 4", "Line 12"])
def test_floor_five_never_falls_back_to_another_railway(name):
    assert not match_faust_hollow_pack(5, name)


def test_floor_five_accepts_line_two_in_english():
    assert match_faust_hollow_pack(5, "Refraction Railway Line 2")


def test_draft_cannot_silently_use_standard_auto_battle_after_import():
    preset = apply_faust_hollow_preset(TeamSetting())
    imported = TeamSetting.model_validate(preset.model_dump())
    with pytest.raises(cannotOperateGameError, match="整局自动执行尚未就绪"):
        ensure_mirror_preset_ready(imported)
    assert ensure_mirror_preset_ready(TeamSetting()) is None


def test_unknown_preset_is_rejected_instead_of_discarded():
    with pytest.raises(ValidationError):
        TeamSetting(mirror_preset="unknown")


def test_script_checks_preset_before_initializing_or_operating_game():
    import ast

    source = Path(__file__).resolve().parents[1] / "tasks/base/script_task_scheme.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    script = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "script_task")
    calls = {
        node.func.id: node.lineno
        for node in ast.walk(script)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls["ensure_mirror_preset_ready"] < calls["init_game"]


def _theme_selector_with_fake_screen(names):
    """运行实际选择函数，隔离截图、鼠标和等待，验证不会误拖其他线路。"""
    import ast
    from types import SimpleNamespace

    source = Path(__file__).resolve().parents[1] / "tasks/mirror/select_theme_pack.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "select_theme_pack")
    function.decorator_list = []

    class FakeAuto:
        def __init__(self):
            self.drags = []
            self.refreshes = 0

        def take_screenshot(self):
            return object()

        def find_element(self, path, **kwargs):
            if path.endswith("theme_pack_features.png"):
                return [(500, 100), (1000, 100)]
            return False

        def find_text_element(self, target, crop, **kwargs):
            return [names[0 if crop[0] < 500 else 1]]

        def mouse_drag_down(self, x, y):
            self.drags.append((x, y))

        def click_element(self, path):
            if path.endswith("refresh_assets.png"):
                self.refreshes += 1
                return True
            return False

        def mouse_to_blank(self, **kwargs):
            pass

    fake_auto = FakeAuto()
    logger = SimpleNamespace(info=lambda *args: None, debug=lambda *args: None, error=lambda *args: None)
    namespace = {
        "auto": fake_auto,
        "cfg": SimpleNamespace(set_win_size=1080, select_event_pack=True, skip_event_pack=True),
        "path_manager": SimpleNamespace(current_language="zh_cn"),
        "theme_list": SimpleNamespace(get_effective_theme_pack_list=lambda *args: {}, preferred_thresholds=999),
        "match_faust_hollow_pack": match_faust_hollow_pack,
        "cannotOperateGameError": cannotOperateGameError,
        "TextMatchResult": type("TextMatchResult", (), {}),
        "log": logger,
        "sleep": lambda *args: None,
        "back_init_menu": lambda: pytest.fail("严格预设不应退回主菜单并继续选其他包"),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["select_theme_pack"], fake_auto


def test_real_selector_ignores_global_event_pack_shortcuts_and_weights():
    select, auto = _theme_selector_with_fake_screen(["Line 4", "Line 2"])
    select(floor=5, mirror_preset="faust_hollow")
    assert auto.drags == [(1000, 100)]
    assert auto.refreshes == 0


def test_real_selector_stops_after_refreshes_without_dragging_other_railway():
    select, auto = _theme_selector_with_fake_screen(["Line 4", "Line 1"])
    with pytest.raises(cannotOperateGameError, match="不会选择其他卡包"):
        select(floor=5, mirror_preset="faust_hollow")
    assert auto.drags == []
    assert auto.refreshes > 0


def test_real_selector_rejects_unknown_floor_before_reading_screen():
    select, auto = _theme_selector_with_fake_screen(["Line 2", "Line 4"])
    with pytest.raises(cannotOperateGameError, match="无法确认当前楼层"):
        select(mirror_preset="faust_hollow")
    assert auto.drags == []
    assert auto.refreshes == 0


def test_real_selector_stops_on_ocr_error_without_retrying_or_falling_back():
    select, auto = _theme_selector_with_fake_screen(["Line 2", "Line 4"])

    def failing_ocr(*args, **kwargs):
        raise RuntimeError("OCR failed")

    auto.find_text_element = failing_ocr
    with pytest.raises(cannotOperateGameError, match="主题包识别出错"):
        select(floor=5, mirror_preset="faust_hollow")
    assert auto.drags == []
    assert auto.refreshes == 0
