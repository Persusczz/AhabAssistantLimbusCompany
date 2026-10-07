from pathlib import Path

FAUST_HOLLOW_IMAGE_DIR = Path(__file__).resolve().parents[2] / "assets/images/default/share/battle/faust_hollow"
FAUST_HOLLOW_IMAGES = {
    "hollow_awakening": "EGO 菜单中的觉醒空洞卡片（避开名称和消耗数字）",
    "hollow_overclock": "长按后 EGO 菜单中的过载空洞卡片",
    "hollow_awakening_selected": "技能栏中已选中的觉醒空洞",
    "hollow_overclock_selected": "技能栏中已选中的过载空洞",
    "ryoshu_guard": "技能栏中黑派良秀的守备技能",
    "enemy_skill_slot": "集中战中可用于拦截的敌方技能槽",
    "railway2_head": "二号线目标的头部技能槽或部位标记",
    "railway2_rose_target": "空洞索敌时玫瑰部位的选中标记（用于检查两处命中）",
}


def faust_hollow_image_path(name: str) -> str:
    if name not in FAUST_HOLLOW_IMAGES:
        raise ValueError(f"未知空洞预设图片：{name}")
    return f"battle/faust_hollow/{name}.png"


def missing_faust_hollow_images() -> list[str]:
    return [f"{name}.png：{description}" for name, description in FAUST_HOLLOW_IMAGES.items()
            if not (FAUST_HOLLOW_IMAGE_DIR / f"{name}.png").is_file()]
