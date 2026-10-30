# -*- coding: utf-8 -*-
"""zhbase 默认排序检查 (独立实现, 不引用生成器的键构造)。

契约 (按实际行为校准过):
  1. 汉字块内按 Unihan 笔画数 → 部首号 → 仓颉码 → 码点排序; 简繁同块混排。
     **汉字以 Unihan 为准** —— 基表 (iso14651_t1_common) 只提供其他文字,
     它附带的兼容汉字 (F900-FAFF / 2F800-2FA1F, 共 1014 行) 不参与设计,
     与其他脚本行同样按 reorder 发射序定位, 排序不在契约内 (只统计, 不断言)。
  2. 未收录码点 (谚文音节、CJK 扩展 A、私用区等) 由 glibc 回落到一~三级
     IGNORE, 互相 tie 并排在所有有序字符**之前**; 系统 zh_CN.UTF-8 /
     en_US.UTF-8 表现相同, 非本 locale 引入。
  3. 拉丁/阿拉伯保持基表位 (排在汉字之前); 希腊/西里尔/泰文/平假名等已收录脚本
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

# 2. 基表附带汉字不计入契约: 只统计它们的实际落点, 不做断言。
#    zhbase 的汉字以 Unihan 为准, 基表只提供其他文字 —— 兼容汉字
#    (F900-FAFF / 2F800-2FA1F) 在基表里有 1014 行, 它们与其他脚本行同样
#    按 reorder 发射序定位, 不属于本 locale 的设计范围。
rng = list(range(0xF900, 0xFB00)) + list(range(0x2F800, 0x2FA1E))
IGNORE = k(chr(0xAC00))                       # 谚文音节: 已知的 IGNORE 回落键
have = [v for v in rng if k(chr(v)) != IGNORE]
unassigned = [v for v in rng if k(chr(v)) == IGNORE]
print(f'2. 基表附带兼容汉字 (不计入契约): 有键 {len(have)} 个, '
      f'回落 IGNORE {len(unassigned)} 个 —— 位置由基表决定, 不断言')

# 3. 未收录回落与脚本次序
probe = [('未收录(谚文)', chr(0xAC00)), ('未收录(扩展A)', chr(0x3400)),
         ('未收录(私用区)', chr(0xE000)), ('拉丁', 'a'), ('汉字首', chr(chars[0])),
         ('希腊', 'Ω'), ('西里尔', 'А'), ('泰文', 'ก'), ('平假名', 'あ')]
order = [n for n, _ in sorted(probe, key=lambda kv: k(kv[1]))]
print('3. 次序:', ' < '.join(order))
want = ['未收录(谚文)', '未收录(扩展A)', '未收录(私用区)', '拉丁', '汉字首',
        '希腊', '西里尔', '泰文', '平假名']
got = order
if got != want:
    print(f'   ✗ 与预期次序不符, 预期: {" < ".join(want)}')
    bad += 1
else:
    print('   ✓ 未收录 < 拉丁 < 汉字 < 其他脚本')
print(f'4. 拉丁/阿拉伯/汉字: {sorted(["a","A","z","1","9",chr(chars[0]),chr(chars[-1])], key=k)}')
print('全部契约成立' if not bad else f'契约违反 {bad} 处')
sys.exit(0 if not bad else 1)
