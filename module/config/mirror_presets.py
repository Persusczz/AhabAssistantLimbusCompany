import re
from pathlib import Path

from ruamel.yaml import YAML

from module.config.config_typing import TeamSetting
from module.config.faust_hollow_assets import missing_faust_hollow_images
from module.my_error.my_error import cannotOperateGameError

FAUST_HOLLOW_PRESET_PATH = Path(__file__).resolve().parents[2] / "assets/config/presets/faust_hollow.yaml"


def load_faust_hollow_plan() -> dict:
    return YAML(typ="safe").load(FAUST_HOLLOW_PRESET_PATH)["preset_plan"]


def apply_faust_hollow_preset(current: TeamSetting) -> TeamSetting:
    """载入已确认的设置；保留游戏内队伍编号和历史统计，重置冲突选项。"""
    data = YAML(typ="safe").load(FAUST_HOLLOW_PRESET_PATH)
    data.pop("preset_plan")
    for field in (
        "team_number",
        "total_mirror_time_hard",
        "mirror_hard_count",
        "total_mirror_time_normal",
        "mirror_normal_count",
    ):
        data[field] = getattr(current, field)
    return TeamSetting.model_validate(data).model_copy(deep=True)


def ensure_mirror_preset_ready(team_setting: TeamSetting) -> None:
    if team_setting.mirror_preset == "faust_hollow":
        plan = load_faust_hollow_plan()
        missing = missing_faust_hollow_images()
        blockers = plan["blockers"] + (["缺少真实游戏识别图片："] + missing if missing else [])
        raise cannotOperateGameError(
            "空洞预设的整局自动执行尚未就绪，已在操作游戏前停止：\n" + "\n".join(blockers)
        )


def match_faust_hollow_pack(floor: int, text: str) -> bool:
    """按楼层匹配；铁路必须识别到独立的线路编号 2。"""
    normalized = re.sub(r"\s+", "", text).lower()
    if floor == 5:
        return bool(re.search(r"(?<!\d)2号线|line2(?!\d)", normalized))
    for entry in load_faust_hollow_plan()["floors"]:
        if entry["floor"] == floor:
            return any(keyword.lower() in normalized for keyword in entry["keywords"])
    return False


def faust_hollow_formation(floor: int) -> list[int]:
    if floor not in range(1, 6):
        raise cannotOperateGameError("空洞预设未识别到有效楼层，无法配队")
    return [0, 1, 0, 2 if floor == 4 else 0, 0, 0, 0, 0, 0, 0, 0, 0]


def faust_hollow_node_weights(floor: int) -> dict[str, int] | None:
    if floor != 3:
        return None
    return {
        "battle": 4, "boss_battle": 6, "event": 1, "shop": 2,
        "focused_encounter": 1000, "risky_encounter": 1000,
        "abnormality_focused_encounter": 200,
    }
