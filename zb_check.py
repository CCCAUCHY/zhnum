# -*- coding: utf-8 -*-
"""zhbase 默认排序检查 (独立实现, 不引用生成器的键构造)。

契约: 汉字块内按 Unihan 笔画数 → 部首号 → 仓颉码 → 码点排序 (简繁同块混排);
兼容汉字紧跟汉字块; 各族文字整块在后; 拉丁保持基表位 (在汉字之下)。
"""
import os, sys, locale, collections
HERE = os.path.dirname(os.path.abspath(__file__))

def cp(s): return int(s[2:], 16)

strokes = {}
for ln in open(os.path.join(HERE, 'unihan-strokes.tsv'), encoding='utf-8'):
    a, b = ln.split('\t'); strokes[cp(a)] = int(b.strip())
rads = {}
for ln in open(os.path.join(HERE, 'unihan-radicals.tsv'), encoding='utf-8'):
    f = ln.split('\t'); rads[cp(f[0])] = int(f[1])
cang = {}
for ln in open(os.path.join(HERE, 'unihan-cangjie.tsv'), encoding='utf-8'):
    a, b = ln.split('\t'); cang[cp(a)] = b.strip()

def expkey(v):
    return (strokes[v], rads.get(v, 999), cang.get(v, 'zzz'), v)

locale.setlocale(locale.LC_ALL, 'zhbase.UTF-8')
from gi.repository import GLib
k = lambda s: GLib.utf8_collate_key_for_filename(s, -1)

# 1. 汉字块内序
chars = sorted(strokes)
by_locale = sorted(chars, key=lambda v: k(chr(v)))
by_spec = sorted(chars, key=expkey)
bad = [(a, b) for a, b in zip(by_locale, by_spec) if a != b]
print(f'1. 汉字块内序: {len(chars)} 字 → 与 (笔画,部首,仓颉,码点) 序差异位置 {len(bad)} 处')
for a, b in bad[:5]:
    print(f'     ✗ 实测序位是 {chr(a)}({expkey(a)}) 应为 {chr(b)}({expkey(b)})')
# 相邻逆序对 (更有意义的口径)
inv = [(by_locale[i-1], by_locale[i]) for i in range(1, len(by_locale))
       if expkey(by_locale[i]) < expkey(by_locale[i-1])]
print(f'   相邻逆序对 {len(inv)} 处')
for a, b in inv[:5]:
    print(f'     ✗ {chr(a)}{expkey(a)} 排在 {chr(b)}{expkey(b)} 之前')

# 2. 块结构: 汉字块 < 兼容汉字 < 其他脚本
def rank(x):
    v = ord(x)
    if v in strokes: return 0
    if 0xF900 <= v <= 0xFAFF or 0x2F800 <= v <= 0x2FA1F: return 1
    return 2
probe = [chr(sorted(strokes)[0]), chr(sorted(strokes)[-1]),
         '豈', '﨎', 'あ', 'Ω', 'А', '가', 'ก']
print('2. 块结构 (末汉字 → 兼容汉字 → 其他脚本):')
seq = sorted(probe, key=lambda c: k(c))
print('   ', ' < '.join(f'{c}(U+{ord(c):04X},块{rank(c)})' for c in seq))
rr = [rank(c) for c in seq]
print('   块号单调不减:', '✓' if rr == sorted(rr) else '✗')

# 3. 拉丁位次 (zhbase 里保持基表位 = 在汉字之下)
print('3. 拉丁/阿拉伯:')
lat = ['a', 'A', 'z', '1', '9', chr(sorted(strokes)[0]), chr(sorted(strokes)[-1]), 'あ']
seq2 = sorted(lat, key=lambda c: k(c))
print('   ', ' < '.join(repr(c) for c in seq2))
