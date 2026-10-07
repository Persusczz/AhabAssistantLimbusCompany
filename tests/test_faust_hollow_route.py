import ast
import heapq
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest

from module.config.mirror_presets import faust_hollow_formation, faust_hollow_node_weights
from module.my_error.my_error import cannotOperateGameError


def _load_map_classes():
    source = Path(__file__).resolve().parents[1] / "tasks/mirror/search_road.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {"MirrorMap", "Row", "Node", "RouteGraph", "all_node_weight", "DEFAULT_WEIGHT", "_position_from_y", "ROAD_ROW_GAP"}
    selected = [node for node in tree.body if
                isinstance(node, ast.ClassDef) and node.name in names or
                isinstance(node, ast.FunctionDef) and node.name in names or
                isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)]
    namespace = {"Enum": Enum, "heapq": heapq, "cfg": SimpleNamespace(set_win_size=1440),
                 "faust_hollow_node_weights": faust_hollow_node_weights,
                 "cannotOperateGameError": cannotOperateGameError,
                 "log": SimpleNamespace(debug=lambda *args: None)}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


def test_floor_three_route_prefers_ordinary_encounter_over_elite():
    classes = _load_map_classes()
    row = classes["Row"]
    nodes = [[ ["battle", (520, 250)], ["risky_encounter", (520, 687)] ]]
    graph = classes["RouteGraph"](nodes, row.MID, (0, 250), node_weights=faust_hollow_node_weights(3))
    graph.init_road([(1, row.MID, row.MID), (1, row.MID, row.BOTTOM)])
    _, path = graph.find_min_weight_route()
    assert path[1].node_class == "battle"
    directions, target_nodes = graph.get_path_directions(path)
    assert len(directions) == len(target_nodes)
    assert target_nodes[0] == "battle"
    assert "bus" not in target_nodes


def test_unavoidable_miniboss_is_preferred_over_elite_chain():
    weights = faust_hollow_node_weights(3)
    assert weights["event"] < weights["battle"] < weights["abnormality_focused_encounter"] < weights["risky_encounter"]
    assert faust_hollow_node_weights(1) is None


def test_map_tracks_nodes_with_directions_without_reusing_previous_floor():
    classes = _load_map_classes()
    classes["search_road_from_road_map"] = lambda **kwargs: (["U", "M"], ["event", "boss_battle"])
    mirror_map = classes["MirrorMap"](mirror_preset="faust_hollow")
    assert mirror_map.get_next_step() == "U"
    assert mirror_map.current_node == "event"
    assert mirror_map.get_next_step() == "M"
    assert mirror_map.current_node == "boss_battle"
    mirror_map.refresh_floor(3)
    assert mirror_map.current_node is None


def test_strict_map_rejects_unknown_node_before_entering():
    classes = _load_map_classes()
    classes["search_road_from_road_map"] = lambda **kwargs: (["M"], ["unknown"])
    mirror_map = classes["MirrorMap"](mirror_preset="faust_hollow")
    with pytest.raises(cannotOperateGameError):
        mirror_map.get_next_step()


@pytest.mark.parametrize("preset", ["standard", "faust_hollow"])
def test_strict_route_cannot_use_bus_shortcut_when_target_position_is_missing(preset):
    classes = _load_map_classes()
    clicked = []
    classes["cfg"].mirror_keyboard_navigation = False
    classes["sleep"] = lambda *args: None

    def click_element(path, **kwargs):
        clicked.append(path)
        return path.endswith("mybus_default_distance.png")

    classes["auto"] = SimpleNamespace(click_element=click_element)
    mirror_map = classes["MirrorMap"](mirror_preset=preset)
    mirror_map._get_next_position = lambda direction: None
    assert mirror_map.enter_next_node("M") is False
    if preset == "faust_hollow":
        assert clicked == []
    else:
        assert clicked[0].endswith("mybus_default_distance.png")


@pytest.mark.parametrize("floor", [1, 2, 3, 5])
def test_solo_faust_formation_outside_floor_four(floor):
    assert faust_hollow_formation(floor) == [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]


def test_floor_four_fields_faust_first_and_ryoshu_second():
    assert faust_hollow_formation(4) == [0, 1, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0]
