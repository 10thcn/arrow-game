# -*- coding: utf-8 -*-
"""
核心逻辑自动化测试。

覆盖作业要求的测试项（T01~T04 的逻辑层）：
    T01 点击前方无阻挡的箭头 -> 能飞出
    T02 点击前方有阻挡的箭头 -> 不能飞出
    T03 点击边缘且朝棋盘外的箭头 -> 能飞出且不越界
    T04 消除本关全部箭头 -> 存在可通关顺序（关卡有解）

运行方式：python test_game.py
"""

import unittest

from main import (LEVELS, board_from_level, can_fly, count_arrows,
                  find_solution)


class TestCanFly(unittest.TestCase):
    """路径检测逻辑测试（对应 T01/T02/T03）。"""

    def test_T01_no_block_can_fly(self):
        # 朝右的箭头，右边到边界之间都是空，应能飞出
        board = board_from_level(["R.."])
        self.assertTrue(can_fly(board, 0, 0))

    def test_T02_blocked_cannot_fly(self):
        # 朝右的箭头，右侧还有另一个箭头，应被阻挡
        board = board_from_level(["R.R."])
        self.assertFalse(can_fly(board, 0, 0))

    def test_T03_edge_outward_no_crash(self):
        # 位于边缘且朝向棋盘外的箭头，正常飞出且不越界
        board = board_from_level([".R.", "...", "..."])
        # (0,1) 朝右，右侧 (0,2) 为空，越过边界即可，不报错
        self.assertTrue(can_fly(board, 0, 1))
        # 左边缘朝左
        board2 = board_from_level(["L.."])
        self.assertTrue(can_fly(board2, 0, 0))
        # 顶行朝上、底行朝下
        board3 = board_from_level(["U..", "...", "..D"])
        self.assertTrue(can_fly(board3, 0, 0))
        self.assertTrue(can_fly(board3, 2, 2))

    def test_four_directions_all_covered(self):
        # 中心箭头分别朝四个方向，且该方向上都无阻挡
        board = board_from_level(["...", ".R.", "..."])
        self.assertTrue(can_fly(board, 1, 1))
        board = board_from_level(["...", ".L.", "..."])
        self.assertTrue(can_fly(board, 1, 1))
        board = board_from_level([".U.", "..."])
        self.assertTrue(can_fly(board, 0, 1))
        board = board_from_level(["...", ".D."])
        self.assertTrue(can_fly(board, 1, 1))


class TestRemove(unittest.TestCase):
    """消除与计数逻辑测试。"""

    def test_remove_decreases_count(self):
        board = board_from_level(["R.R"])
        self.assertEqual(count_arrows(board), 2)
        # 模拟消除最右的箭头（朝右可飞出）
        board[0][2] = '.'
        self.assertEqual(count_arrows(board), 1)

    def test_T06_restart_restores_layout(self):
        # 重新开始 = 重新生成初始棋盘，布局应恢复到初始状态
        level = LEVELS[0]
        b1 = board_from_level(level)
        total = count_arrows(b1)
        # 找到第一个箭头并消除
        for r in range(len(b1)):
            for c in range(len(b1[0])):
                if b1[r][c] in 'URDL':
                    b1[r][c] = '.'
                    break
            else:
                continue
            break
        self.assertEqual(count_arrows(b1), total - 1)
        b2 = board_from_level(level)   # 重新开始
        self.assertEqual(count_arrows(b2), total)
        self.assertEqual(b2, board_from_level(level))   # 布局完整恢复
        # 失误次数恢复由 Game.restart_level 中 mistakes=MAX_MISTAKES 保证


class TestLevelsSolvable(unittest.TestCase):
    """关卡可解性测试（对应 T04：消除全部箭头能通关）。"""

    def test_all_levels_solvable(self):
        for i, level in enumerate(LEVELS, start=1):
            board = board_from_level(level)
            sol = find_solution(board)
            self.assertIsNotNone(sol, f"第 {i} 关无解！")
            self.assertEqual(len(sol), count_arrows(board),
                             f"第 {i} 关的解法没有覆盖全部箭头")
            # 逐字验证解法的每一步都合法：当前箭头确能飞出
            b = board_from_level(level)
            for (r, c) in sol:
                self.assertTrue(can_fly(b, r, c),
                                f"第 {i} 关解法中 ({r},{c}) 这一步被阻挡")
                b[r][c] = '.'
            self.assertEqual(count_arrows(b), 0, f"第 {i} 关按解法未清空棋盘")


if __name__ == "__main__":
    unittest.main(verbosity=2)
