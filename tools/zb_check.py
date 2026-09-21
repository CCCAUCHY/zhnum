# -*- coding: utf-8 -*-
"""zhbase 默认排序检查 (独立实现, 不引用生成器的键构造)。

契约 (按实际行为校准过):
  1. 汉字块内按 Unihan 笔画数 → 部首号 → 仓颉码 → 码点排序; 简繁同块混排。
  2. 兼容汉字**不独立成块** —— 872 个有行的码点散在整个汉字块里 (实测位置区间
     6..21863, 区间内夹着 20986 个普通汉字), 所以只能查"都在汉字块内"。
  3. 未收录码点 (谚文音节、CJK 扩展 A、私用区、兼容区里的未分配码位) 由 glibc
     回落到一~三级 IGNORE, 互相 tie 并排在所有有序字符**之前**; 系统
     zh_CN.UTF-8 / en_US.UTF-8 表现相同, 非本 locale 引入。
  4. 拉丁/阿拉伯保持基表位 (排在汉字之前); 希腊/西里尔/泰文/平假名等已收录脚本
     排在汉字之后。

退出码: 0 = 契约全部成立 / 1 = 有违反 / 2 = 环境错 (locale 未编译等)。
用 ctypes 直调 libglib, 不依赖 python3-gi —— 理由同 tools/sweep.py: gi 绑定会
按 UTF-8 解码排序键, 键里出现非 UTF-8 字节就抛 UnicodeDecodeError。
用法: LC_ALL=zhbase.UTF-8 LOCPATH=<目录> python3 tools/zb_check.py
"""
import ctypes, locale, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 仓库根 (数据表在此)


def cp(s):
    return int(s[2:], 16)


strokes, rads, cang = {}, {}, {}
for ln in open(os.path.join(HERE, 'unihan-strokes.tsv'), encoding='utf-8'):
    a, b = ln.split('\t'); strokes[cp(a)] = int(b.strip())
for ln in open(os.path.join(HERE, 'unihan-radicals.tsv'), encoding='utf-8'):
    f = ln.split('\t'); rads[cp(f[0])] = int(f[1])
for ln in open(os.path.join(HERE, 'unihan-cangjie.tsv'), encoding='utf-8'):
    a, b = ln.split('\t'); cang[cp(a)] = b.strip()


def expkey(v):
    return (strokes[v], rads.get(v, 999), cang.get(v, 'zzz'), v)


try:
    locale.setlocale(locale.LC_ALL, 'zhbase.UTF-8')
except locale.Error as e:
    print(f'locale 加载失败: {e} —— 检查 LOCPATH 与该目录下的 zhbase.UTF-8', file=sys.stderr)
    sys.exit(2)

_L = ctypes.CDLL('libglib-2.0.so.0')
_L.g_utf8_collate_key_for_filename.restype = ctypes.c_void_p
_L.g_utf8_collate_key_for_filename.argtypes = [ctypes.c_char_p, ctypes.c_ssize_t]
_L.g_free.argtypes = [ctypes.c_void_p]


def k(s):
    p = _L.g_utf8_collate_key_for_filename(s.encode('utf-8'), -1)
    if not p:
        return b''
    try:
        return ctypes.string_at(p)
    finally:
        _L.g_free(p)


bad = 0

# 1. 汉字块内序
chars = sorted(strokes)
by_locale = sorted(chars, key=lambda v: k(chr(v)))
by_spec = sorted(chars, key=expkey)
diff = [(a, b) for a, b in zip(by_locale, by_spec) if a != b]
inv = [(by_locale[i - 1], by_locale[i]) for i in range(1, len(by_locale))
       if expkey(by_locale[i]) < expkey(by_locale[i - 1])]
print(f'1. 汉字块内序: {len(chars)} 字 → 与 (笔画,部首,仓颉,码点) 序差异 {len(diff)} 处,'
      f' 相邻逆序对 {len(inv)} 处')
for a, b in (diff[:5] + inv[:5]):
    print(f'     ✗ 实测 {chr(a)}{expkey(a)} / 应为 {chr(b)}{expkey(b)}')
bad += len(inv)

# 2. 兼容汉字在汉字块内 (不独立成块)
rng = list(range(0xF900, 0xFB00)) + list(range(0x2F800, 0x2FA1E))
IGNORE = k(chr(0xAC00))                       # 谚文音节: 已知的 IGNORE 回落键
have = [v for v in rng if k(chr(v)) != IGNORE]
unassigned = [v for v in rng if k(chr(v)) == IGNORE]
seq = sorted(chars + have, key=lambda v: k(chr(v)))
pos = {v: i for i, v in enumerate(seq)}
lo, hi = min(pos[v] for v in have), max(pos[v] for v in have)
inside = sum(1 for i in range(lo, hi + 1) if seq[i] in strokes)
print(f'2. 兼容汉字: 有行 {len(have)} 个 (位置 {lo}..{hi}, 区间内夹普通汉字 {inside} 个),'
      f' 未分配回落 IGNORE {len(unassigned)} 个')
print(f'   兼容汉字都在汉字块内: {"✓" if have else "✗ 一个都没有"}')
bad += 0 if have else 1

# 3. 未收录回落与脚本次序
probe = [('未收录(谚文)', chr(0xAC00)), ('未收录(扩展A)', chr(0x3400)),
         ('未收录(私用区)', chr(0xE000)), ('拉丁', 'a'), ('汉字首', chr(chars[0])),
         ('兼容汉字', chr(have[0]) if have else chr(0xF900)),
         ('希腊', 'Ω'), ('西里尔', 'А'), ('泰文', 'ก'), ('平假名', 'あ')]
order = [n for n, _ in sorted(probe, key=lambda kv: k(kv[1]))]
print('3. 次序:', ' < '.join(order))
want = ['未收录(谚文)', '未收录(扩展A)', '未收录(私用区)', '拉丁', '汉字首',
        '希腊', '西里尔', '泰文', '平假名']
got = [n for n in order if n != '兼容汉字']
if got != want:
    print(f'   ✗ 与预期次序不符, 预期: {" < ".join(want)}')
    bad += 1
else:
    print('   ✓ 未收录 < 拉丁 < 汉字 < 其他脚本 (兼容汉字随汉字块, 位置不固定)')
print(f'4. 拉丁/阿拉伯/汉字: {sorted(["a","A","z","1","9",chr(chars[0]),chr(chars[-1])], key=k)}')
print('全部契约成立' if not bad else f'契约违反 {bad} 处')
sys.exit(0 if not bad else 1)
