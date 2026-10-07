import ast
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from module.config.config_typing import TeamSetting
from module.my_error.my_error import cannotOperateGameError


ROOT = Path(__file__).resolve().parents[1]


def _load_function(path, name, namespace):
    source = ROOT / path
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    function.decorator_list = []
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


def _battle_loop(monkeypatch, state="standby", timeout=False):
    import sys

    monkeypatch.setitem(sys.modules, "tasks.base.retry", SimpleNamespace(check_times=lambda *args, **kwargs: timeout))

    class Screen:
        def __init__(self):
            self.state = state
            self.clicks = []

        def take_screenshot(self):
            return object()

        def get_restore_time(self):
            return None

        def find_element(self, path, **kwargs):
            return (self.state == "standby" and path.endswith("more_information_assets.png") or
                    self.state == "dead" and path.endswith("dead_all.png"))

        def click_element(self, path, **kwargs):
            self.clicks.append(path)
            return self.state == "finish" and path.endswith("battle_finish_confirm_assets.png")

    screen = Screen()
    normal_calls = []

    def normal_battle(**kwargs):
        normal_calls.append(kwargs)
        screen.state = "finish"
        return False

    battle = SimpleNamespace(
        INIT_CHANCE=16, running=True, first_battle=False, is_tool=True,
        identify_keyword_turn=True, mouse_click_rate=False, defense_all_time=False,
        _update_wait_time=lambda *args: 1, _battle_operation=normal_battle,
    )
    namespace = {
        "auto": screen, "cfg": SimpleNamespace(fight_to_last_man=True),
        "log": SimpleNamespace(debug=lambda *args: None), "time": time,
        "sleep": lambda *args: None, "Callable": Callable,
        "DefenseForSoloState": type("DefenseForSoloState", (), {}),
        "cannotOperateGameError": cannotOperateGameError,
    }
    function = _load_function("tasks/battle/battle.py", "fight", namespace)
    return function, battle, screen, normal_calls


def test_actual_battle_loop_calls_preset_instead_of_standard_operation(monkeypatch):
    function, battle, screen, normal_calls = _battle_loop(monkeypatch)
    calls = []

    def preset_turn():
        calls.append("preset")
        screen.state = "finish"

    assert function(battle, turn_handler=preset_turn, choice_event_handling=False) is None
    assert calls == ["preset"]
    assert normal_calls == []


def test_preset_error_escapes_loop_without_standard_fallback(monkeypatch):
    function, battle, screen, normal_calls = _battle_loop(monkeypatch)

    def preset_turn():
        raise cannotOperateGameError("缺少空洞图片")

    with pytest.raises(cannotOperateGameError, match="缺少空洞图片"):
        function(battle, turn_handler=preset_turn)
    assert screen.state == "standby"
    assert normal_calls == []


@pytest.mark.parametrize(("state", "timeout"), [("dead", False), ("standby", True)])
def test_failure_and_timeout_never_restart_preset_battle(monkeypatch, state, timeout):
    function, battle, screen, normal_calls = _battle_loop(monkeypatch, state, timeout)
    with pytest.raises(cannotOperateGameError):
        function(battle, turn_handler=lambda: pytest.fail("不应继续战斗"))
    assert screen.clicks == []
    assert normal_calls == []


def test_standard_battle_keeps_original_operation(monkeypatch):
    function, battle, screen, normal_calls = _battle_loop(monkeypatch)
    function(battle, choice_event_handling=False)
    assert len(normal_calls) == 1


@pytest.mark.parametrize("preset", ["standard", "faust_hollow"])
def test_mirror_error_only_retries_standard_task(preset):
    class FailedMirror:
        def __init__(self, *args):
            pass

        def run(self):
            raise cannotOperateGameError("识别失败")

    namespace = {
        "TeamSetting": TeamSetting, "Mirror": FailedMirror,
        "cfg": SimpleNamespace(auto_hard_mirror=False),
        "log": SimpleNamespace(exception=lambda *args: None),
    }
    function = _load_function("tasks/base/script_task_scheme.py", "onetime_mir_process", namespace)
    setting = TeamSetting(mirror_preset=preset)
    if preset == "faust_hollow":
        with pytest.raises(cannotOperateGameError, match="识别失败"):
            function(setting, 1)
    else:
        assert function(setting, 1) is False
