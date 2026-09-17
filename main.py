# -*- coding: utf-8 -*-
"""
一箭又一箭（Arrow by Arrow）
============================

一个点击式箭头解谜小游戏，福州大学《软件工程》课程第二次个人作业。

玩法规则
--------
1. 棋盘中每个箭头有 上/下/左/右 四种方向之一；
2. 用鼠标点击某个箭头：
   - 若该箭头前进方向上（同一行/同一列）到棋盘边界之间没有其他箭头，
     则该箭头飞出棋盘并被消除；
   - 若前进方向上存在其他箭头阻挡，则该箭头发生碰撞，消耗一次失误机会；
3. 消除当前关卡全部箭头后进入下一关；
4. 失误次数耗尽时本关失败，可重新开始。

开发环境
--------
- Python 3.12
- Pygame 2.6

AIGC 工具
---------
- Claude Code（Anthropic）
"""

import math
import os
import sys

import pygame

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------

# 方向字符 -> 坐标增量（列, 行），屏幕坐标系 y 向下
DIR_VEC = {
    'U': (0, -1),   # 上
    'R': (1, 0),    # 右
    'D': (0, 1),    # 下
    'L': (-1, 0),   # 左
}
# 方向字符 -> 绘制时的旋转角度（度）
DIR_ANGLE = {'U': -90, 'R': 0, 'D': 90, 'L': 180}
# 每个方向对应的箭头颜色，便于玩家区分方向
DIR_COLOR = {
    'U': (102, 204, 102),   # 上：绿
    'R': (240, 160, 80),    # 右：橙
    'D': (90, 160, 240),    # 下：蓝
    'L': (220, 120, 200),   # 左：粉
}

MAX_MISTAKES = 3            # 每关允许的失误次数

WIDTH, HEIGHT = 800, 660    # 窗口尺寸
FPS = 60

# 界面配色
BG = (28, 30, 46)           # 背景
PANEL = (40, 43, 66)        # 格子底色
GRID = (72, 76, 110)        # 网格线
TEXT = (232, 234, 242)      # 主文字
TEXT_DIM = (150, 154, 176)  # 次要文字
COLLIDE = (240, 90, 90)     # 碰撞提示色
HINT = (255, 220, 90)       # 提示高亮色

# 游戏状态
STATE_START = 'start'
STATE_PLAY = 'play'
STATE_CLEAR = 'clear'
STATE_FAIL = 'fail'

# ----------------------------------------------------------------------------
# 关卡数据
# ----------------------------------------------------------------------------
# 每一关用字符串列表表示，字符含义：U 上、R 右、D 下、L 左、. 空
# 箭头方向与位置交错分布，每关都由求解器验证可通关（见 test_game.py）。
LEVELS = [
    # 第 1 关（5×5，12 箭头）：方向交错，观察路径即可找到飞出顺序
    [
        ".RU.R",
        "DU...",
        "..L..",
        ".L.UR",
        ".LD.D",
    ],
    # 第 2 关（6×6，18 箭头）：棋盘更大、箭头更密
    [
        "..LURU",
        "LU...U",
        "L..D.D",
        "..RD.R",
        ".UR..D",
        "..L.D.",
    ],
    # 第 3 关（7×7，24 箭头）：四个方向交错分布
    [
        "L.R.U.R",
        "...U.UR",
        "..L..R.",
        "L..UDD.",
        ".L..DLR",
        "U..D.D.",
        "L.RD.D.",
    ],
    # 第 4 关（7×7，28 箭头，最难）：方向数量均衡，需统筹安排
    [
        "LU.LL..",
        "UU.U..R",
        ".DUUR.R",
        "DDDL.UR",
        "...L..D",
        ".L.R.R.",
        "LD..DR.",
    ],
]

# ----------------------------------------------------------------------------
# 核心逻辑（纯函数，便于单元测试）
# ----------------------------------------------------------------------------


def board_from_level(level):
    """把字符串关卡转换为可变棋盘（list of list of char）。"""
    return [list(row) for row in level]


def rows_cols(board):
    return len(board), len(board[0])


def count_arrows(board):
    """统计棋盘上剩余的箭头数量。"""
    return sum(1 for row in board for ch in row if ch in DIR_VEC)


def can_fly(board, r, c):
    """
    判断 (r, c) 处的箭头能否飞出。

    规则：沿箭头前进方向逐格前进，直到越过棋盘边界；
    途中若遇到任何其他箭头（非空），则被阻挡，返回 False；
    顺利到达边界则返回 True。
    """
    ch = board[r][c]
    if ch not in DIR_VEC:
        return False
    dc, dr = DIR_VEC[ch]
    rows, cols = rows_cols(board)
    rr, cc = r + dr, c + dc
    while 0 <= rr < rows and 0 <= cc < cols:
        if board[rr][cc] != '.':
            return False
        rr += dr
        cc += dc
    return True


def find_solution(board):
    """
    用深度优先搜索求一个可通关的消除顺序。

    返回一个 [(r, c), ...] 列表（消除顺序）；若无解返回 None。
    用于：(1) 验证关卡确实可通关；(2) 实现“提示”功能。
    """
    board = [row[:] for row in board]
    rows, cols = rows_cols(board)
    remaining = [(r, c) for r in range(rows) for c in range(cols)
                 if board[r][c] in DIR_VEC]
    seen = set()

    def dfs(b, rest, path):
        if not rest:
            return path
        key = tuple(tuple(row) for row in b)
        if key in seen:
            return None
        seen.add(key)

        movable = [(r, c) for (r, c) in rest if can_fly(b, r, c)]
        for (r, c) in movable:
            nb = [row[:] for row in b]
            nb[r][c] = '.'
            new_rest = [a for a in rest if a != (r, c)]
            res = dfs(nb, new_rest, path + [(r, c)])
            if res is not None:
                return res
        return None

    return dfs(board, remaining, [])


# ----------------------------------------------------------------------------
# 动画数据结构
# ----------------------------------------------------------------------------


class FlyAnim:
    """箭头飞出棋盘的动画：从格子中心沿方向平移，移出棋盘后结束。"""

    def __init__(self, direction, center, bounds, speed=14):
        self.direction = direction
        self.x, self.y = center
        self.speed = speed
        self.bounds = bounds      # (left, top, right, bottom)
        self.alive = True

    def update(self):
        dc, dr = DIR_VEC[self.direction]
        self.x += dc * self.speed
        self.y += dr * self.speed
        left, top, right, bottom = self.bounds
        if self.x < left or self.x > right or self.y < top or self.y > bottom:
            self.alive = False


class ShakeAnim:
    """箭头被阻挡时的碰撞反馈：沿前进方向来回晃动并变红，持续约 0.5 秒。"""

    DURATION = 500  # 毫秒

    def __init__(self, r, c, direction, start_ms):
        self.r, self.c = r, c
        self.direction = direction
        self.start = start_ms
        self.alive = True

    def offset(self, now_ms):
        """返回当前帧的像素偏移量 (dx, dy)。"""
        elapsed = now_ms - self.start
        if elapsed >= self.DURATION:
            self.alive = False
            return 0, 0
        ratio = 1 - elapsed / self.DURATION      # 振幅随时间衰减到 0
        amp = 7 * ratio
        dc, dr = DIR_VEC[self.direction]
        wave = math.sin(elapsed / 1000 * 40)     # 高频来回
        return dc * amp * wave, dr * amp * wave


# ----------------------------------------------------------------------------
# 游戏主类
# ----------------------------------------------------------------------------


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("一箭又一箭")
        self.clock = pygame.time.Clock()
        self.font_large = get_font(40)
        self.font_mid = get_font(28)
        self.font_small = get_font(20)

        self.state = STATE_START
        self.level_index = 0
        self.board = None
        self.rows = self.cols = 0
        self.mistakes = MAX_MISTAKES
        self.flying = []      # 正在飞出动画的箭头
        self.shaking = []     # 正在碰撞动画的箭头
        self.pending_fail_ms = None   # 延迟进入失败状态的时间戳
        self.hint = None      # 提示：建议下一步消除的格子 (r, c)

        # 布局（在进入关卡时重新计算）
        self.board_x = self.board_y = 0
        self.cell = 0

        # 按钮矩形
        self.btn_restart = pygame.Rect(0, 0, 150, 44)
        self.btn_hint = pygame.Rect(0, 0, 150, 44)

    # ---- 关卡装载 ----
    def load_level(self, index):
        self.level_index = index
        self.board = board_from_level(LEVELS[index])
        self.rows, self.cols = rows_cols(self.board)
        self.mistakes = MAX_MISTAKES
        self.flying.clear()
        self.shaking.clear()
        self.pending_fail_ms = None
        self.hint = None
        self.state = STATE_PLAY
        self._calc_layout()

    def restart_level(self):
        self.load_level(self.level_index)

    def _calc_layout(self):
        """根据棋盘行列数计算格子大小和棋盘左上角，使棋盘居中。"""
        margin = 24
        top_area = 96          # 顶部状态栏高度
        bottom_area = 80       # 底部按钮区高度
        avail_w = WIDTH - margin * 2
        avail_h = HEIGHT - top_area - bottom_area
        self.cell = max(20, min(avail_w // self.cols, avail_h // self.rows))
        bw = self.cell * self.cols
        bh = self.cell * self.rows
        self.board_x = (WIDTH - bw) // 2
        self.board_y = top_area + (avail_h - bh) // 2

        # 底部两个按钮水平居中排布
        gap = 30
        total = self.btn_restart.w * 2 + gap
        start_x = (WIDTH - total) // 2
        self.btn_restart.topleft = (start_x, HEIGHT - 62)
        self.btn_hint.topleft = (start_x + self.btn_restart.w + gap, HEIGHT - 62)

    # ---- 交互 ----
    def on_click(self, mx, my):
        if self.state == STATE_START:
            self.load_level(0)
            return
        if self.state == STATE_CLEAR:
            if self.level_index + 1 < len(LEVELS):
                self.load_level(self.level_index + 1)
            else:
                self.state = STATE_START   # 全部通关后回到开始界面
            return
        if self.state == STATE_FAIL:
            self.restart_level()
            return

        # 游戏中：优先处理按钮
        if self.btn_restart.collidepoint(mx, my):
            self.restart_level()
            return
        if self.btn_hint.collidepoint(mx, my):
            self._show_hint()
            return

        # 点击棋盘格子
        if not (self.board_x <= mx < self.board_x + self.cell * self.cols
                and self.board_y <= my < self.board_y + self.cell * self.rows):
            return
        c = int((mx - self.board_x) // self.cell)
        r = int((my - self.board_y) // self.cell)
        self.hint = None
        self._click_arrow(r, c)

    def _click_arrow(self, r, c):
        ch = self.board[r][c]
        if ch not in DIR_VEC:
            return
        if can_fly(self.board, r, c):
            # 飞出：移除并启动飞行动画
            self.board[r][c] = '.'
            center = self._cell_center(r, c)
            bounds = (self.board_x - 40, self.board_y - 40,
                      self.board_x + self.cell * self.cols + 40,
                      self.board_y + self.cell * self.rows + 40)
            self.flying.append(FlyAnim(ch, center, bounds))
        else:
            # 碰撞：播放晃动动画，并扣一次失误
            self.shaking.append(ShakeAnim(r, c, ch, pygame.time.get_ticks()))
            self.mistakes -= 1
            if self.mistakes <= 0:
                # 延迟 0.5 秒，让碰撞反馈可见后再进入失败
                self.pending_fail_ms = pygame.time.get_ticks() + 500

    def _show_hint(self):
        sol = find_solution(self.board)
        self.hint = sol[0] if sol else None

    def _cell_center(self, r, c):
        return (self.board_x + c * self.cell + self.cell // 2,
                self.board_y + r * self.cell + self.cell // 2)

    # ---- 更新 ----
    def update(self):
        now = pygame.time.get_ticks()
        for f in self.flying:
            f.update()
        self.flying = [f for f in self.flying if f.alive]

        for s in self.shaking:
            s.offset(now)          # 触发 alive 标记更新
        self.shaking = [s for s in self.shaking if s.alive]

        # 通关判定：飞行动画结束且棋盘已空
        if self.state == STATE_PLAY and not self.flying and count_arrows(self.board) == 0:
            self.state = STATE_CLEAR

        # 延迟失败
        if (self.state == STATE_PLAY and self.pending_fail_ms
                and now >= self.pending_fail_ms):
            self.state = STATE_FAIL
            self.pending_fail_ms = None

    # ---- 绘制 ----
    def draw(self):
        self.screen.fill(BG)
        if self.state == STATE_START:
            self._draw_start()
        elif self.state == STATE_PLAY:
            self._draw_play()
        elif self.state == STATE_CLEAR:
            self._draw_play()          # 棋盘背景保留
            self._draw_overlay("通关！", f"第 {self.level_index + 1} 关完成",
                               "点击进入下一关" if self.level_index + 1 < len(LEVELS)
                               else "点击返回开始界面")
        elif self.state == STATE_FAIL:
            self._draw_play()
            self._draw_overlay("失败！", "失误次数耗尽", "点击重新开始")
        pygame.display.flip()

    def _draw_start(self):
        title = self.font_large.render("一箭又一箭", True, TEXT)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 200)))
        desc = [
            "点击箭头：前方无阻挡则飞出，有阻挡则碰撞并扣除失误",
            "清空全部箭头即可通关，失误耗尽则失败",
            "共 %d 关，每关 %d 次失误机会" % (len(LEVELS), MAX_MISTAKES),
        ]
        for i, line in enumerate(desc):
            surf = self.font_small.render(line, True, TEXT_DIM)
            self.screen.blit(surf, surf.get_rect(center=(WIDTH // 2, 270 + i * 34)))
        self._draw_button(self.font_mid, "开始游戏", self._center_rect(200, 56, WIDTH // 2, 380))

    def _draw_play(self):
        # 顶部状态栏
        info = [
            "第 %d / %d 关" % (self.level_index + 1, len(LEVELS)),
            "剩余箭头：%d" % count_arrows(self.board),
            "剩余失误：%d" % self.mistakes,
        ]
        total_w = 0
        for t in info:
            total_w += self.font_mid.size(t)[0]
        total_w += 80 * (len(info) - 1)
        x = (WIDTH - total_w) // 2
        for t in info:
            surf = self.font_mid.render(t, True, TEXT)
            self.screen.blit(surf, (x, 40))
            x += surf.get_width() + 80

        # 棋盘格子
        for r in range(self.rows):
            for c in range(self.cols):
                rect = pygame.Rect(self.board_x + c * self.cell,
                                   self.board_y + r * self.cell,
                                   self.cell, self.cell)
                pygame.draw.rect(self.screen, PANEL, rect)
                pygame.draw.rect(self.screen, GRID, rect, 1)

        # 提示高亮
        if self.hint:
            r, c = self.hint
            rect = pygame.Rect(self.board_x + c * self.cell,
                               self.board_y + r * self.cell,
                               self.cell, self.cell)
            pygame.draw.rect(self.screen, HINT, rect, 4)

        now = pygame.time.get_ticks()
        # 静止箭头
        for r in range(self.rows):
            for c in range(self.cols):
                ch = self.board[r][c]
                if ch not in DIR_VEC:
                    continue
                cx, cy = self._cell_center(r, c)
                color = DIR_COLOR[ch]
                # 碰撞中的箭头：偏移 + 变红
                for s in self.shaking:
                    if s.r == r and s.c == c:
                        dx, dy = s.offset(now)
                        cx += dx
                        cy += dy
                        color = COLLIDE
                        break
                draw_arrow(self.screen, (cx, cy), ch, self.cell * 0.62, color)

        # 飞出动画中的箭头
        for f in self.flying:
            draw_arrow(self.screen, (f.x, f.y), f.direction,
                       self.cell * 0.62, DIR_COLOR[f.direction])

        # 底部按钮
        self._draw_button(self.font_small, "重新开始", self.btn_restart)
        self._draw_button(self.font_small, "提示", self.btn_hint)

    def _draw_overlay(self, title, subtitle, action):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 12, 20, 170))
        self.screen.blit(overlay, (0, 0))
        t = self.font_large.render(title, True, TEXT)
        self.screen.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))
        s = self.font_mid.render(subtitle, True, TEXT)
        self.screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10)))
        a = self.font_small.render(action, True, TEXT_DIM)
        self.screen.blit(a, a.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))

    def _draw_button(self, font, text, rect):
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, GRID, rect, 2, border_radius=8)
        surf = font.render(text, True, TEXT)
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    @staticmethod
    def _center_rect(w, h, cx, cy):
        return pygame.Rect(cx - w // 2, cy - h // 2, w, h)

    # ---- 主循环 ----
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.on_click(*event.pos)
            self.update()
            self.draw()
            self.clock.tick(FPS)


# ----------------------------------------------------------------------------
# 绘制辅助
# ----------------------------------------------------------------------------

_FONT_CACHE = {}

# Windows 常见中文字体文件路径（按优先级排列）。
# 直接用文件路径加载，规避 pygame.match_font 在部分 Windows 机器上
# 枚举字体注册表时抛 TypeError 的问题。
_FONT_PATHS = [
    "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",    # 黑体
    "C:/Windows/Fonts/simsun.ttc",    # 宋体
    "C:/Windows/Fonts/msjh.ttc",      # 微软正黑体
    "C:/Windows/Fonts/Deng.ttf",      # 等线
]


def get_font(size):
    """加载中文字体，避免中文显示为方框；找不到时退回默认字体。"""
    if size not in _FONT_CACHE:
        font = None
        for path in _FONT_PATHS:
            if os.path.exists(path):
                try:
                    font = pygame.font.Font(path, size)
                    break
                except Exception:
                    font = None
        if font is None:
            font = pygame.font.Font(None, size)
        _FONT_CACHE[size] = font
    return _FONT_CACHE[size]


def draw_arrow(surface, center, direction, size, color):
    """
    用多边形绘制一个箭头。先构造“朝右”的箭头顶点，再按方向旋转。
    顶点以箭头中心为原点，size 为箭头总长度。
    """
    s = size / 2.0
    # 朝右箭头的顶点（闭合多边形）
    base = [
        (-s, -s / 3),   # 杆左上
        (s / 2, -s / 3),  # 杆右上
        (s / 2, -s * 2 / 3),  # 头上
        (s, 0),          # 头尖
        (s / 2, s * 2 / 3),   # 头下
        (s / 2, s / 3),  # 杆右下
        (-s, s / 3),     # 杆左下
    ]
    angle = math.radians(DIR_ANGLE[direction])
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    cx, cy = center
    points = []
    for x, y in base:
        rx = x * cos_a - y * sin_a
        ry = x * sin_a + y * cos_a
        points.append((cx + rx, cy + ry))
    pygame.draw.polygon(surface, color, points)


def main():
    Game().run()


if __name__ == "__main__":
    main()
