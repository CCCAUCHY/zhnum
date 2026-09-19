# -*- coding: utf-8 -*-
"""Nautilus 路径 500 文件排序性能。
Nautilus 的排序做法 = 每个文件名算一次 GLib 文件名排序键 (逐键缓存), 之后按键
比较。此处按同样口径测: 500 个键的生成耗时 + 按键排序耗时。
"""
import sys, os, time, random, locale
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zhnum_core import read

locale.setlocale(locale.LC_ALL, 'zhnum.UTF-8')
from gi.repository import GLib
key = lambda s: GLib.utf8_collate_key_for_filename(s, -1)

random.seed(1)
NAMES = [read(random.randint(10**7, 10**8 - 1)) + '.txt' for _ in range(500)]
NAMES += [f'{i}.txt' for i in range(1, 26)]
NAMES += ['第一百章.txt', '第一章.txt', '报告.txt', 'IMG_0001.png', 'v10.txt', 'v2.txt']
NAMES = NAMES[:500] if len(NAMES) >= 500 else NAMES
print(f'语料: {len(NAMES)} 个文件名, 平均 {sum(len(n) for n in NAMES)//len(NAMES)} 字')

def bench(reps=5):
    # 预热 (locale 装载)
    [key(n) for n in NAMES[:20]]
    best = None
    for _ in range(reps):
        t0 = time.perf_counter()
        ks = [(key(n), n) for n in NAMES]          # 逐键生成 (Nautilus 缓存口径)
        t1 = time.perf_counter()
        ks.sort()                                   # 按键比较
        t2 = time.perf_counter()
        v = (t1 - t0, t2 - t1, t2 - t0)
        if best is None or v[2] < best[2]:
            best = v
    return best

kg, st, tot = bench()
print(f'  键生成 {kg*1000:7.1f} ms   排序 {st*1000:6.1f} ms   合计 {tot*1000:7.1f} ms')
print(f'  (每键 {(kg/len(NAMES))*1e6:.1f} μs)')
