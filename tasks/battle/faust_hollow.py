import re
from time import sleep

from module.config.faust_hollow_assets import faust_hollow_image_path
from module.my_error.my_error import cannotOperateGameError


def parse_turn(text: str) -> int | None:
    match = re.fullmatch(r"\s*(?:turn|回合)?\s*(\d{1,2})\s*", text, re.IGNORECASE)
    return int(match[1]) if match else None


class FaustHollowTurnController:
    """一场战斗独立计数；只有确认进入交战后才记为已执行。"""

    def __init__(self, floor: int, ui):
        if floor not in range(1, 6):
            raise cannotOperateGameError("空洞预设未识别到有效楼层")
        self.floor = floor
        self.ui = ui
        self.last_turn = 0

    def __call__(self) -> None:
        turn = self.ui.read_turn()
        if turn not in (1, 2) or turn < self.last_turn:
            raise cannotOperateGameError(f"空洞预设回合识别异常或超出两回合流程：{turn}")
        if turn == self.last_turn:
            return
        self.ui.select_hollow("overclock" if self.floor <= 3 else "awakening")
        if self.floor == 4 and turn == 1:
            self.ui.intercept_with_ryoshu()
        if self.floor == 5 and turn == 2:
            self.ui.target_head()
        if not self.ui.start_turn():
            raise cannotOperateGameError("空洞预设未进入交战，已停止，未改用普通胜率操作")
        self.last_turn = turn


class FaustHollowBattleUI:
    """使用真实 UI 模板操作；所有步骤校验后才允许按下开始。"""

    def __init__(self, automation, scale: float, turn_bbox):
        self.auto = automation
        self.scale = scale
        self.turn_bbox = turn_bbox
        self.ego_position = None

    def _snapshot(self):
        if self.auto.take_screenshot() is None:
            raise cannotOperateGameError("空洞预设无法取得游戏截图")

    def read_turn(self):
        self._snapshot()
        return parse_turn(" ".join(self.auto.get_text_from_screenshot(self.turn_bbox)))

    def _find_image(self, name, crop=None):
        position = self.auto.find_element(
            faust_hollow_image_path(name), threshold=0.9, model="aggressive", my_crop=crop,
        )
        # 单目标匹配返回裁切内坐标，多目标匹配则已在 Automation 中恢复偏移。
        if position and crop:
            return position[0] + crop[0], position[1] + crop[1]
        return position

    def _require_image(self, name, crop=None):
        for _ in range(3):
            self._snapshot()
            if position := self._find_image(name, crop):
                return position
            sleep(0.3)
        raise cannotOperateGameError(f"空洞预设未识别到 {name}.png，已停止")

    def _skill_slots(self):
        left = self.auto.find_element("battle/gear_left.png", threshold=0.9)
        right = self.auto.find_element("battle/gear_right.png", threshold=0.9)
        if not left or not right:
            raise cannotOperateGameError("空洞预设未识别到技能栏齿轮")
        count = int((right[0] - left[0] - 200 * self.scale) / (145 * self.scale))
        if not 1 <= count <= 12:
            raise cannotOperateGameError(f"空洞预设技能槽数量异常：{count}")
        # 沿用 Battle._calculate_skills_position 的横向标定；头像位于守备行上方。
        slots = [(left[0] + (220 - 4.5 * count + 161 * i) * self.scale,
                  left[1] + 180 * self.scale) for i in range(count)]
        return left, slots

    def _slot_crop(self, position):
        width, height = self.auto.screenshot.size
        x, y = position
        return (max(0, int(x - 78 * self.scale)), max(0, int(y - 300 * self.scale)),
                min(width, int(x + 78 * self.scale)), min(height, int(y + 100 * self.scale)))

    def select_hollow(self, mode):
        if mode not in ("awakening", "overclock"):
            raise cannotOperateGameError(f"空洞预设不支持的 EGO 模式：{mode}")
        # 先分配其他普通技能；在验证指定 EGO 之前不会开始交战。
        self.auto.key_press("p")
        self._snapshot()
        _, slots = self._skill_slots()
        avatar = slots[0]
        self.auto.mouse_drag(*avatar, drag_time=1, dx=0, dy=0, move_back=False)
        card = self._require_image("hollow_awakening")
        if self._find_image("hollow_overclock"):
            raise cannotOperateGameError("空洞菜单模板无法区分觉醒与过载，请重新标定图片")
        if mode == "overclock":
            self.auto.mouse_drag(*card, drag_time=1, dx=0, dy=0, move_back=False)
            self._snapshot()
            if overclock_card := self._find_image("hollow_overclock"):
                self.auto.mouse_click(*overclock_card)
        else:
            self.auto.mouse_click(*card)
        crop = self._slot_crop(avatar)
        self.ego_position = self._require_image(f"hollow_{mode}_selected", crop)
        opposite = "overclock" if mode == "awakening" else "awakening"
        if self._find_image(f"hollow_{opposite}_selected", crop):
            raise cannotOperateGameError("已选 EGO 模板无法区分觉醒与过载，已停止")

    def intercept_with_ryoshu(self):
        self._snapshot()
        left, slots = self._skill_slots()
        if len(slots) != 2:
            raise cannotOperateGameError("第四层首回合必须只有浮士德、良秀两个出战技能槽")
        guard_crop = self._slot_crop(slots[1])
        self.auto.mouse_click(slots[1][0], left[1] + 250 * self.scale)
        guard = self._require_image("ryoshu_guard", guard_crop)
        width, height = self.auto.screenshot.size
        targets = self.auto.find_element(
            faust_hollow_image_path("enemy_skill_slot"), find_type="image_with_multiple_targets",
            threshold=0.9, my_crop=(0, 0, width, int(height * 0.6)), min_dist=int(50 * self.scale),
        )
        if not targets:
            raise cannotOperateGameError("第四层未识别到可拦截的敌方技能槽")
        target = sorted(targets, key=lambda position: (position[0], position[1]))[0]
        self.auto.mouse_drag_link([guard, target])
        self.auto.mouse_to_blank()
        self._require_image("ryoshu_guard", guard_crop)

    def target_head(self):
        if self.ego_position is None:
            raise cannotOperateGameError("第五层尚未确认选中空洞")
        width, height = self.auto.screenshot.size
        enemy_crop = (0, 0, width, int(height * 0.65))
        head = self._require_image("railway2_head", enemy_crop)
        self.auto.mouse_drag_link([self.ego_position, head])
        self.auto.mouse_to_blank()
        self._snapshot()
        targets = self.auto.find_element(
            faust_hollow_image_path("railway2_rose_target"), find_type="image_with_multiple_targets",
            threshold=0.9, my_crop=enemy_crop, min_dist=int(80 * self.scale),
        )
        if not targets or len(targets) < 2:
            raise cannotOperateGameError("第五层未确认玫瑰两个部位均被索敌，已停止")

    def start_turn(self):
        if self.ego_position is None:
            raise cannotOperateGameError("空洞未选中，禁止开始交战")
        self.auto.key_press("enter")
        for _ in range(6):
            self._snapshot()
            if self.auto.find_element("battle/pause_assets.png"):
                return True
            sleep(0.3)
        return False
