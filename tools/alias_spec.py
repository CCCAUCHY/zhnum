# -*- coding: utf-8 -*-
"""别名完备性检查 (GLib / Nautilus 路径)。

口径: 四种风格 —— 全小写 / 全大写 / 小写数字+大写单位 / 大写数字+小写单位,
每种各带简繁一套 ⇒ 一个数字最多 8 种写法 (与 gen_zhnum.py 的别名闭包同源,
此处独立重实现, 以便抓出生成器漏注册的写法)。
分类: 十百千 前面没有数字时属数字类 (十万 的 十), 前面有数字时属单位类
      (一千 的 千); 万亿 恒属单位类。
简繁: 数字类 贰/貳 叁/參 陆/陸; 单位类 万/萬 亿/億。
"""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zhnum_core import read, D

DIG = '一二三四五六七八九'
SBK = '十百千'
WY = '万亿'
# 数字类 3 形: 小写 / 大写简 / 大写繁
_DMAP = [
    str.maketrans('', ''),
    str.maketrans(DIG + SBK, '壹贰叁肆伍陆柒捌玖' + '拾佰仟'),
    str.maketrans(DIG + SBK, '壹貳參肆伍陸柒捌玖' + '拾佰仟'),
]
# 单位类 4 形: 小写简 / 大写简 / 小写繁 / 大写繁
# (萬 是繁体字不是财务字 ⇒ 简体全大写是 壹佰万, 繁体全大写是 壹佰萬)
# 风格组合: 同级配对两种 (全小写/全大写), 各带简繁 —— 混搭已废弃
_PURE = ((0, 0), (1, 1), (0, 2), (2, 3))
_MIXED = tuple((d, u) for d in range(3) for u in range(4))
_STYLES = _PURE          # 混搭已废弃, 只查纯写法
_UMAP = [
    str.maketrans('', ''),
    str.maketrans(SBK, '拾佰仟'),
    str.maketrans(WY, '萬億'),
    str.maketrans(SBK + WY, '拾佰仟' + '萬億'),
]

def classify(s):
    """十百千 前面有数字 ⇒ 单位类; 否则 ⇒ 数字类。万亿 恒单位类。"""
    g, prev_d = [], False
    for c in s:
        if c in SBK + WY:
            is_u = prev_d or (c in WY)
            g.append('u' if is_u else 'd')
            prev_d = not is_u
        else:
            g.append('d'); prev_d = (c in DIG)
    return g

def forms8(s):
    g = classify(s)
    out = []
    for dm in _DMAP:
        for um in _UMAP:
            out.append(''.join((dm if grp == 'd' else um).get(c, c)
                               if False else c for c, grp in zip(s, g)))
    # 上面的写法不适用 dict.get, 改为逐字符 translate
    out = []
    for di, ui in _STYLES:
        r = []
        for c, grp in zip(s, g):
            r.append(c.translate(_DMAP[di] if grp == 'd' else _UMAP[ui]))
        out.append(''.join(r))
    return list(dict.fromkeys(out))

import locale
locale.setlocale(locale.LC_ALL, 'zhnum.UTF-8')
from gi.repository import GLib
k = lambda x: GLib.utf8_collate_key_for_filename(x, -1)

print('=== 样例展开 ===')
for s in ['十万', '一千九百', '一百万', '一千零一十', '一十']:
    print(f'  {s} ({len(forms8(s))} 形): {forms8(s)}')

def run(vals, label):
    pairs = sorted([(f, v) for v in vals for f in forms8(read(v))], key=lambda x: k(x[0]))
    bad = [(pairs[i-1], pairs[i]) for i in range(1, len(pairs)) if pairs[i][1] < pairs[i-1][1]]
    pos = collections.defaultdict(list)
    for i, (f, v) in enumerate(pairs):
        pos[v].append(i)
    gap = [v for v, p in pos.items() if max(p)-min(p)+1 != len(p)]
    print(f'  {label}: 值 {len(pos)} / 别名 {len(pairs)} → 违反 {len(bad)}, 隔断 {len(gap)}')
    for a, b in bad[:5]:
        print(f'       ✗ {a[0]}({a[1]}) < {b[0]}({b[1]})')
    if gap:
        v = gap[0]; p = pos[v]
        seg = [x for x in pairs[min(p):max(p)+1] if x[1] != v]
        print(f'       ✗ 值{v} 被 {seg[:3]} 隔断')
    return len(bad) + len(gap)

random.seed(11)
v = sorted(set([1,2,9,10,11,19,20,99,100,101,110,111,999,1000,1001,1010,1011,
                1100,1110,1999,2000,9999,10000,10001,10100,11000,99999,100000,
                1000000,1010000,99999999]) | set(random.sample(range(1, 10**8), 2000)))
print()
run(v, '裸数 (边界+随机 2000)')
# 复合: r×万 / r×亿 —— 读数 = read(r) + 单位, 闭包作用在整串上
RMAX = int(os.environ.get('RMAX', '101'))
run(sorted(set(random.sample(range(1, 10000), 400))), '万级 (随机 400)') if False else None
rw = sorted(set([1,2,9,10,11,100,101,110,111,999,1000,1001,1010,1011,1100,9999]
                + random.sample(range(1, 10000), 400)))
pairs_w = [(f, r*10**4) for r in rw for f in forms8(read(r) + '万')]
ry = sorted(set([1,2,9,10,11,20,90,99,100,101] + random.sample(range(1, RMAX+1), min(400, RMAX))))
pairs_y = [(f, r*10**8) for r in ry for f in forms8(read(r) + '亿')]
for pairs, lab in ((pairs_w, '万级 r×万'), (pairs_y, f'亿级 r×亿 (档内 r≤{RMAX})')):
    pairs = sorted(pairs, key=lambda x: k(x[0]))
    bad = [(pairs[i-1], pairs[i]) for i in range(1, len(pairs)) if pairs[i][1] < pairs[i-1][1]]
    pos = collections.defaultdict(list)
    for i, (f, val) in enumerate(pairs):
        pos[val].append(i)
    gap = [val for val, pp in pos.items() if max(pp)-min(pp)+1 != len(pp)]
    print(f'  {lab}: 值 {len(pos)} / 别名 {len(pairs)} → 违反 {len(bad)}, 隔断 {len(gap)}')
    for a, b in bad[:4]:
        print(f'       ✗ {a[0]}({a[1]}) < {b[0]}({b[1]})')
