import pytest
import importlib.util
from pathlib import Path

from module.my_error.my_error import cannotOperateGameError
source = Path(__file__).resolve().parents[1] / "tasks/battle/faust_hollow.py"
spec = importlib.util.spec_from_file_location("faust_hollow_battle", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FaustHollowTurnController = module.FaustHollowTurnController
parse_turn = module.parse_turn
FaustHollowBattleUI = module.FaustHollowBattleUI


class FakeBattleUI:
    def __init__(self, turn=1):
        self.turn = turn
        self.actions = []
        self.fail_selection = False
        self.started = True

    def read_turn(self):
        return self.turn

    def select_hollow(self, mode):
        self.actions.append(("ego", mode))
        if self.fail_selection:
            raise cannotOperateGameError("空洞未装备")

    def intercept_with_ryoshu(self):
        self.actions.append(("guard", "ryoshu"))

    def target_head(self):
        self.actions.append(("target", "head"))

    def start_turn(self):
        self.actions.append(("start", self.turn))
        return self.started


@pytest.mark.parametrize("floor", [1, 2, 3])
def test_early_floors_overclock_and_duplicate_frame_cannot_spend_ego_twice(floor):
    ui = FakeBattleUI()
    controller = FaustHollowTurnController(floor, ui)
    controller()
    controller()
    assert ui.actions == [("ego", "overclock"), ("start", 1)]
    ui.turn = 2
    controller()
    assert ui.actions[-2:] == [("ego", "overclock"), ("start", 2)]


def test_floor_four_only_first_turn_intercepts_and_uses_awakening():
    ui = FakeBattleUI()
    controller = FaustHollowTurnController(4, ui)
    controller()
    ui.turn = 2
    controller()
    assert ui.actions == [
        ("ego", "awakening"), ("guard", "ryoshu"), ("start", 1),
        ("ego", "awakening"), ("start", 2),
    ]


def test_floor_five_resume_on_turn_two_still_targets_head():
    ui = FakeBattleUI(turn=2)
    FaustHollowTurnController(5, ui)()
    assert ui.actions == [("ego", "awakening"), ("target", "head"), ("start", 2)]


@pytest.mark.parametrize("turn", [None, -1, 0, 3, 10])
def test_unknown_or_extra_round_never_starts_battle(turn):
    ui = FakeBattleUI(turn)
    with pytest.raises(cannotOperateGameError):
        FaustHollowTurnController(4, ui)()
    assert ui.actions == []


def test_selection_failure_and_unverified_start_do_not_retry_as_normal_battle():
    ui = FakeBattleUI()
    ui.fail_selection = True
    with pytest.raises(cannotOperateGameError):
        FaustHollowTurnController(1, ui)()
    assert ui.actions == [("ego", "overclock")]
    ui = FakeBattleUI()
    ui.started = False
    with pytest.raises(cannotOperateGameError, match="未进入交战"):
        FaustHollowTurnController(1, ui)()


def test_round_number_cannot_move_backwards():
    ui = FakeBattleUI(turn=2)
    controller = FaustHollowTurnController(1, ui)
    controller()
    ui.turn = 1
    with pytest.raises(cannotOperateGameError):
        controller()


@pytest.mark.parametrize(("text", "expected"), [("TURN 1", 1), ("turn\n2", 2), ("2", 2), ("回合 1", 1), ("", None), ("HP 12", None), ("TURN I", None), ("1 2", None)])
def test_turn_ocr_requires_an_unambiguous_round_number(text, expected):
    assert parse_turn(text) == expected


class FakeScreen:
    def __init__(self):
        from types import SimpleNamespace

        self.screenshot = SimpleNamespace(size=(2560, 1440))
        self.state = "standby"
        self.mode = "awakening"
        self.keys = []
        self.links = []
        self.slots = 1
        self.missing_card = False
        self.ambiguous = False
        self.guard = False
        self.head = False
        self.rose_count = 2

    def take_screenshot(self):
        return self.screenshot

    def get_text_from_screenshot(self, crop):
        return ["TURN", "1"]

    def key_press(self, key):
        self.keys.append(key)
        if key == "enter":
            self.state = "started"

    def mouse_drag(self, x, y, **kwargs):
        if (x, y) == (800, 400):
            self.mode = "overclock"
        else:
            self.state = "menu"

    def mouse_click(self, x, y):
        if (x, y) == (800, 400):
            self.state = "selected"
        else:
            self.guard = True

    def mouse_drag_link(self, positions):
        self.links.append(positions)
        if positions[-1] == (1000, 300):
            self.head = True

    def mouse_to_blank(self):
        pass

    def find_element(self, path, **kwargs):
        name = Path(path).stem
        if name == "gear_left":
            return (400, 600)
        if name == "gear_right":
            return (600 + 145 * self.slots, 600)
        if name in ("hollow_awakening", "hollow_overclock") and self.state == "menu" and not self.missing_card:
            return (800, 400) if name == f"hollow_{self.mode}" or self.ambiguous else None
        if name.endswith("_selected") and self.state == "selected":
            return (50, 100) if name == f"hollow_{self.mode}_selected" or self.ambiguous else None
        if name == "ryoshu_guard" and self.guard:
            return (50, 100)
        if name == "enemy_skill_slot":
            return [(1200, 300)]
        if name == "railway2_head":
            return (1000, 300)
        if name == "railway2_rose_target" and self.head:
            return [(1000 + index * 100, 300) for index in range(self.rose_count)]
        if name == "pause_assets" and self.state == "started":
            return (100, 100)
        return None


@pytest.mark.parametrize("mode", ["awakening", "overclock"])
def test_ui_verifies_requested_ego_in_skill_slot_before_enter(monkeypatch, mode):
    monkeypatch.setattr(module, "sleep", lambda *args: None)
    screen = FakeScreen()
    ui = FaustHollowBattleUI(screen, 1, (20, 123, 210, 193))
    assert ui.read_turn() == 1
    ui.select_hollow(mode)
    assert screen.keys == ["p"]
    assert ui.ego_position is not None
    assert ui.start_turn() is True
    assert screen.keys == ["p", "enter"]


@pytest.mark.parametrize("failure", ["missing_card", "ambiguous"])
def test_missing_or_ambiguous_ego_image_never_presses_enter(monkeypatch, failure):
    monkeypatch.setattr(module, "sleep", lambda *args: None)
    screen = FakeScreen()
    setattr(screen, failure, True)
    with pytest.raises(cannotOperateGameError):
        FaustHollowBattleUI(screen, 1, (20, 123, 210, 193)).select_hollow("awakening")
    assert screen.keys == ["p"]


def test_guard_only_changes_second_slot_and_links_one_enemy_skill(monkeypatch):
    monkeypatch.setattr(module, "sleep", lambda *args: None)
    screen = FakeScreen()
    screen.slots = 2
    ui = FaustHollowBattleUI(screen, 1, (20, 123, 210, 193))
    ui.select_hollow("awakening")
    ego_position = ui.ego_position
    ui.intercept_with_ryoshu()
    assert ui.ego_position == ego_position
    assert len(screen.links) == 1
    assert screen.links[0][-1] == (1200, 300)
    assert screen.keys == ["p"]


def test_head_target_rejects_only_one_confirmed_rose_part(monkeypatch):
    monkeypatch.setattr(module, "sleep", lambda *args: None)
    screen = FakeScreen()
    screen.rose_count = 1
    ui = FaustHollowBattleUI(screen, 1, (20, 123, 210, 193))
    ui.select_hollow("awakening")
    with pytest.raises(cannotOperateGameError, match="两个部位"):
        ui.target_head()
    assert screen.links[0][-1] == (1000, 300)
    assert screen.keys == ["p"]
