from pathlib import Path

FAUST_HOLLOW_IMAGE_DIR = Path(__file__).resolve().parents[2] / "assets/images/default/share/battle/faust_hollow"
FAUST_HOLLOW_IMAGES = {
    "hollow_awakening": "EGO 菜单中的空洞图案（验证身份，模式另行校验）",
    "hollow_overclock": "长按后 EGO 菜单中的过载空洞卡片",
    "hollow_awakening_selected": "技能栏中已选中的觉醒空洞",
    "hollow_overclock_selected": "技能栏中的 OVERCLOCK 标记（需配合空洞菜单身份校验）",
    "ryoshu_guard": "技能栏中黑派良秀的守备技能",
    "enemy_skill_slot": "集中战中可用于拦截的敌方技能槽",
    "railway2_head": "二号线目标的头部技能槽或部位标记",
    "railway2_rose_target": "空洞索敌时玫瑰部位的选中标记（用于检查两处命中）",
}

# 已收到但尚未确认觉醒/过载状态的原生 UI 样本，不计入启动所需模板。
FAUST_HOLLOW_REFERENCE_IMAGES = {
    "hollow_menu_entry": "横向空洞条目的图案（不含中文名称）",
    "hollow_skill_gold": "金光技能图：觉醒/过载与悬停状态待确认",
    "hollow_skill_blue": "蓝色技能图：觉醒/过载与悬停状态待确认",
}


def faust_hollow_image_path(name: str) -> str:
    if name not in FAUST_HOLLOW_IMAGES:
        raise ValueError(f"未知空洞预设图片：{name}")
    return f"battle/faust_hollow/{name}.png"


def missing_faust_hollow_images() -> list[str]:
    return [f"{name}.png：{description}" for name, description in FAUST_HOLLOW_IMAGES.items()
            if not (FAUST_HOLLOW_IMAGE_DIR / f"{name}.png").is_file()]
