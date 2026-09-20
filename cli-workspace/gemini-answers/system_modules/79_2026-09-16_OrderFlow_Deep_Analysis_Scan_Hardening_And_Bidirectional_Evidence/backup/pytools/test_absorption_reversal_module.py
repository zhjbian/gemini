# -*- coding: utf-8 -*-
"""吸收反转判定器（`order_flow_analysis/absorption_reversal.py` · PAIR v1.1）契约测试（2026-09-15）。

锁定口径（只用 2026-09-14 / 2026-09-15 两个相反案例标定）：
  1. 锚点可分：09-14 07:54（真反转）→ 门槛 PASS / +9/9 / A型 / OPEN_BULLISH；
                09-15 07:53（假反弹）→ 门槛 BLOCK（±15 分钟累计 Delta ≤ 0）/ 不参与。
  2. 硬门槛必须拦住「结构像 A 但净流反向」的失败低点（09-14 07:19 / 07:24）。
  3. 假反弹日全天不得产出任何开仓动作。
  4. 实盘路径：数据只到 t+45~t+90 时自动降级为 8 维投票（门槛 6），仍可判定；
     盘口缺失时降级为 6 维投票（门槛 4）。
  5. 镜像（高点派发）方向恒为 BEARISH。

运行：`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 PyTools/option_seller/test_absorption_reversal_module.py`
"""
import os
import sys
import unittest

proj_dir = '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading'
pytools_dir = os.path.join(proj_dir, 'PyTools')
for _d in [proj_dir, pytools_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

from order_flow_analysis import absorption_reversal as AR  # noqa: E402

# 整日复算结果缓存（原始文件解析开销大：确保每个 (day, mode) 只算一次）
_DAY_CACHE = {}


def day_results(day, mode='low'):
    key = (day, mode)
    if key not in _DAY_CACHE:
        _DAY_CACHE[key] = AR.evaluate_day(day, AR.load_templates(), mode=mode)
    return _DAY_CACHE[key]

A_DAY, A_T, A_PX = '2026-09-14', '07:54', 7664.00
B_DAY, B_T, B_PX = '2026-09-15', '07:53', 7643.50


class TestAnchors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tpl = AR.load_templates()
        cls.trades_a = AR.load_trades_from_raw(A_DAY)
        cls.trades_b = AR.load_trades_from_raw(B_DAY)
        cls.dom_a = AR.dom_minutes_from_raw(A_DAY)
        cls.dom_b = AR.dom_minutes_from_raw(B_DAY)

    def _eval(self, trades, dom, hm, px):
        return AR.evaluate_candidate(trades, dom, AR.sec_of(hm), px, self.tpl, 'low')

    def test_templates_carry_two_anchors(self):
        self.assertIn('A', self.tpl)
        self.assertIn('B', self.tpl)
        self.assertEqual(self.tpl['anchors']['A']['day'], A_DAY)
        self.assertEqual(self.tpl['anchors']['B']['day'], B_DAY)
        for k in ('into30_net', 'cvd_delta_30m', 'mid30_net', 'zone_span',
                  'dom_ask_near_min', 'dom_bid_near_min', 'dom_tot_max', 'vwap_reclaim'):
            self.assertIn(k, self.tpl['A'])
            self.assertIn(k, self.tpl['B'])

    def test_true_reversal_anchor_passes(self):
        r = self._eval(self.trades_a, self.dom_a, A_T, A_PX)
        self.assertTrue(r['gate_ok'], 'A 锚点必须通过净流硬门槛')
        self.assertEqual(r['verdict'], 'A型')
        self.assertEqual(r['score'], 9)
        self.assertEqual(r['n_dims'], 9)
        self.assertEqual(r['action'], 'OPEN_BULLISH')
        self.assertEqual(r['direction'], 'BULLISH')

    def test_false_bounce_anchor_blocked(self):
        r = self._eval(self.trades_b, self.dom_b, B_T, B_PX)
        self.assertFalse(r['gate_ok'], 'B 锚点必须被净流硬门槛拦下')
        self.assertEqual(r['verdict'], '不参与')
        self.assertEqual(r['action'], 'NONE')
        self.assertLess(r['cvd_delta_30m'], 0)

    def test_gate_blocks_structurally_a_like_failures(self):
        """09-14 07:19 / 07:24：投票也是 +7（结构像 A），但净流反向 ⇒ 必须拦下。"""
        for hm, px in (('07:19', 7681.00), ('07:24', 7671.25)):
            r = self._eval(self.trades_a, self.dom_a, hm, px)
            self.assertFalse(r['gate_ok'], f'{hm} 应被硬门槛拦下')
            self.assertEqual(r['verdict'], '不参与')
            self.assertEqual(r['action'], 'NONE')
            self.assertGreaterEqual(r['score'], 6, f'{hm} 结构性投票仍偏高（这正是需要门槛的原因）')

    def test_false_bounce_day_never_opens(self):
        for r in day_results(B_DAY):
            self.assertNotEqual(r['action'], 'OPEN_BULLISH', f"假反弹日不得产出开仓：{r['t']}")
            self.assertNotEqual(r['verdict'], 'A型', f"假反弹日不得判 A 型：{r['t']}")

    def test_true_reversal_day_opens_only_at_absorbed_lows(self):
        res = [r for r in day_results(A_DAY) if r['action'] == 'OPEN_BULLISH']
        self.assertEqual(sorted(r['t'] for r in res), ['07:40', '07:54'])


class TestLivePathDegradation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tpl = AR.load_templates()
        cls.trades = AR.load_trades_from_raw(A_DAY)
        cls.dom = AR.dom_minutes_from_raw(A_DAY)

    def test_half_window_drops_next45_dim(self):
        """数据只到 t+46 分钟：next45 未满窗 ⇒ 不投票（8 维），否则会把半窗 0 误投给 B 模板。"""
        now = AR.sec_of('08:40')                      # 07:54 + 46 分钟
        tr = [x for x in self.trades if x[0] <= now]
        dm = [d for d in self.dom if d['min'] <= now // 60]
        r = AR.evaluate_candidate(tr, dm, AR.sec_of(A_T), A_PX, self.tpl, 'low', now_sec=now)
        self.assertFalse(r['next45_ready'])
        self.assertIsNone(r['next45_net'])
        self.assertEqual(r['n_dims'], 8)
        self.assertEqual(r['need'], 6)
        self.assertTrue(r['gate_ok'])
        self.assertEqual(r['verdict'], 'A型')

    def test_full_window_restores_nine_dims(self):
        now = AR.sec_of('09:30')
        tr = [x for x in self.trades if x[0] <= now]
        dm = [d for d in self.dom if d['min'] <= now // 60]
        r = AR.evaluate_candidate(tr, dm, AR.sec_of(A_T), A_PX, self.tpl, 'low', now_sec=now)
        self.assertTrue(r['next45_ready'])
        self.assertEqual(r['n_dims'], 9)
        self.assertEqual(r['score'], 9)

    def test_missing_dom_degrades_to_six_dims(self):
        r = AR.evaluate_candidate(self.trades, [], AR.sec_of(A_T), A_PX, self.tpl, 'low')
        self.assertFalse(r['dom_available'])
        self.assertEqual(r['n_dims'], 6)
        self.assertEqual(r['need'], 4)
        self.assertTrue(r['gate_ok'])
        self.assertEqual(r['verdict'], 'A型')


class TestMirror(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tpl = AR.load_templates()
        cls.trades = AR.load_trades_from_raw(B_DAY)

    def test_high_side_direction_is_bearish(self):
        res = day_results(B_DAY, 'high')
        self.assertTrue(res, '高点侧应能检出候选')
        for r in res:
            self.assertEqual(r['direction'], 'BEARISH')
            self.assertIn(r['action'], ('OPEN_BEARISH', 'NONE'))

    def test_high_side_no_short_when_gate_blocked(self):
        for r in day_results(B_DAY, 'high'):
            if r['action'] == 'OPEN_BEARISH':
                self.assertTrue(r['gate_ok'], f"未过门槛不得开仓：{r['t']}")


class TestContract(unittest.TestCase):
    def test_contract_shape(self):
        tpl = AR.load_templates()
        res = day_results(A_DAY)
        pick = [r for r in res if r['verdict'] == 'A型'][0]
        c = AR.to_contract(pick, enabled=False)
        for k in ('version', 'available', 'enabled', 'candidate_time', 'candidate_px', 'direction',
                  'gate_ok', 'score', 'n_dims', 'need', 'verdict', 'action', 'dom_available', 'dims', 'votes'):
            self.assertIn(k, c)
        self.assertEqual(c['version'], AR.PAIR_VERSION)
        self.assertTrue(c['available'])
        self.assertFalse(c['enabled'])

    def test_contract_empty_state(self):
        c = AR.to_contract(None)
        self.assertFalse(c['available'])
        self.assertIn('reason', c)


if __name__ == '__main__':
    unittest.main(verbosity=2)
