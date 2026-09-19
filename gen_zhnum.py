#!/usr/bin/env python3
"""生成 zhbase + zhnum locale 源文件.

zhnum 的 LC_COLLATE 通过 copy "zhbase" 引用默认排序 (换默认排序只改
zhbase, zhnum 自动跟随):

  zhbase — 默认排序源. 全部汉字(含数字字)单块: 块内 笔画数 kTotalStrokes
      → 部首 kRSUnicode → 仓颉 kCangjie → 码点; 汉字行后追加兼容汉字行与
      脚本行 (基表非空一级元素整体提升, 中文连块). 被 zhnum 引用的契约:
      ① 单块结构 + 汉字行后兼容汉字/脚本行  ② 数字字按普通汉字进块
      (zhnum 用数值槽覆盖)  ③ 汉字行二级 <BASE> + 四级 <U0021> (借基表
      符号 — zhnum 位置机制的前提, 见下)  ④ 其余 LC 类别 copy zh_CN.
  zhnum  — copy "zhbase" + 单 reorder 块叠加数值覆盖 (无汉字行):
      首字序 = 拉丁 < 数字(值序) < 汉字(单块默认序) < 其他脚本
      (GLib 文件名路径: 阿拉伯 < 拉丁 < 中文连块 < 其他脚本).

      核心语义: 位置敏感族键 — N篇 (量词=篇, 序数标记=空) 与 篇N (序数
      标记=篇, 量词=空) 是不同族, 不混排; 同(序数标记,量词)族聚族 (含空),
      族内纯数值序; 同值写法不等值 — 按值序相邻, 值内按注册序
      (一 < 壹 < 1 < 二, 第十章 < 第10章, strcoll ≠ 0).

      机制 (四个权重层, 键按 1→2→3→4 逐层裁决):
      - 权重1 骨架聚族: 数字槽一级 IGNORE, 骨架相同的短语 (一篇/篇一/
        十篇…) 一至三级全部相等, 比较进入权重4;
      - 数值槽在权重4: 基表 (iso14651_t1_common) 各节四级带 position 修饰
        且随 copy 传播 (只能借四级: position 须所有节同级), 四级 = 逐原子
        位置列比较 ⇒ 数字位置可见 — 同骨架族内按数字位置分子族 (骨架先
        行的子族在前 ⇒ 篇N < N篇), 子族内按数值序; 前缀对正确 (第十章 <
        第十一章) 靠 zhbase 汉字行四级 <U0021> — 权重序 基表符号 < 本地
        reorder 新符号 < copy 链块符号, 汉字行若用自身 token 会被 copy 链
        符号压过 (列上 汉字 > 数值槽, 反向分区), 必须借基表低权符号;
      - 权重2 影子: 槽/拉丁行 = IGNORE;<自身>;IGNORE;<槽>, 汉字行权重2 =
        <BASE> (基表 collating-symbol, あ 行二级同款, 值 02) — 权重2 与
        权重4 同构 (骨架列低权 + 槽列按值+注册序) ⇒ strxfrm 语义不变,
        位置分区在权重2 保持; GLib 文件名键形 01 eX… (首非空层在第 2 字
        节 > 数字段标记 02) ⇒ 阿拉伯 < 拉丁 < 中文连块 < 其他脚本.
        标记必须引 collating-symbol 而非字符 token: 字符作权重 = 元素值
        的新分配 (落进引用块值域并重排整个值空间);
      - 权重3 恒 IGNORE: 若带值, 会在数值/位置裁决前插入一层与基表不对称
        的比较, 打断位置分区.

用法: python3 gen_zhnum.py TIER OUTDIR
  TIER   完美范围上限 (10**n; 0 = 不做全量枚举, 大数单位链注册到 1e36).
         分档 = ① 基础注册 (系数/口语/省零/带零化合物) 值 < TIER
         ② 单位 u < TIER 才整体保留 (原子与全部乘积同进退: 原子 vs
         [系数][单位] 混排必错序, 故按单位整取整舍; 上界位 骨架族化 ⇒
         原子 < 族 恒对: 九千九百九十九万 < 一亿)
         ③ u < TIER 时全量枚举 r×u (r ≤ TIER//u, 1..9999 全部读法)
  OUTDIR 输出目录 (zhbase 各档同内容, 每档目录自含便于 localedef)

已知限制 (详见 README): 值超 TIER 的串退多原子近似; 阿拉伯数字不进数值
  槽 (strxfrm 路径走脚本自然位, GLib 路径由 GLib 数字段自编码成自然序);
  廿/卅/俩/初 等其余口语数词当普通汉字; 口语三字形贪心抢同前缀省零读法
  (二万五十 > 二万一百), 已知且接受.

编译: cd <OUTDIR> && localedef -i zhbase -f UTF-8 ./loc/zhbase.UTF-8
                     && localedef -i zhnum  -f UTF-8 ./loc/zhnum.UTF-8
      (zhnum 编译时 localedef 从 cwd 找到 zhbase 源; 安装后从
       /usr/share/i18n/locales 找到, 两文件必须一起安装)
验证: LC_ALL=zhnum.UTF-8  LOCPATH=<OUTDIR>/loc python3 verify.py
      LC_ALL=zhbase.UTF-8 LOCPATH=<OUTDIR>/loc python3 verify.py
安装: 详见 README (zhnum 以符号链接指向 tiers/<档>, 切档只改链接)
副产物: slot-order.tsv — 全部槽写法按发射序 (verify 同值不等值检查基准)
"""
import re
import sys

# ---- 参数化: python3 gen_zhnum.py TIER OUTDIR ----
if len(sys.argv) < 3:
    sys.exit('用法: python3 gen_zhnum.py TIER OUTDIR [pure|mixed]\n'
             '  TIER  完美范围上限 10**n (0 = 不枚举)\n'
             '  OUTDIR 输出目录\n'
             '  pure  只注册全小写/全大写两套写法 (体积约一半)\n'
             '  mixed 再加 小写数字+大写单位 / 大写数字+小写单位 两套 (默认)')
TIER = int(sys.argv[1])
OUTDIR = sys.argv[2]
STYLES = sys.argv[3] if len(sys.argv) > 3 else 'mixed'
from zhnum_core import (TRUNC_LIMIT, read, u,
                        D, FIN, FIN_T, TR, TR_T, TRF_, TRFT_,
                        TRD_, TRDT_, TRU_,
                        alias_closure as _alias_closure)

def alias_closure(s):
    """本档写法版本的闭包 (STYLES 来自命令行第三参数)"""
    return _alias_closure(s, STYLES)

def in_tier(v):
    return TIER == 0 or v <= TIER      # 含端点: 亿亿档 = 一亿亿(1e16)以内完美

OUT_ZHNUM = f"{OUTDIR}/zhnum"
OUT_ZHBASE = f"{OUTDIR}/zhbase"
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
STROKES_FILE = _HERE + '/unihan-strokes.tsv'    # kTotalStrokes 基本区
RADICALS_FILE = _HERE + '/unihan-radicals.tsv'  # kRSUnicode
CANGJIE_FILE = _HERE + '/unihan-cangjie.tsv'    # kCangjie 全 BMP
ISO_FILE = '/usr/share/i18n/locales/iso14651_t1_common'   # 基表 (脚本行来源; 发行版恒在)

# ---- 汉字基座: 键 = (笔画数, 部首号, 仓颉码, 码点) ----
strokes = {}
for line in open(STROKES_FILE, encoding='utf-8'):
    a, b = line.split('\t')
    strokes[int(a[2:], 16)] = int(b)
ints = {}
for line in open(RADICALS_FILE, encoding='utf-8'):
    a, b, c = line.split('\t')
    ints[int(a[2:], 16)] = (int(b), int(c))
cangjie = {}
for line in open(CANGJIE_FILE, encoding='utf-8'):
    a, b = line.rstrip('\n').split('\t')
    cangjie[int(a[2:], 16)] = b
# 全部汉字进块 (含数字字 — zhnum 引用时用数值槽覆盖它们)

def hanzi_row(v, s):
    ch = chr(v)
    rad = ints.get(v, (999, 999))[0]
    cj = cangjie.get(v, 'zzz')          # 无仓颉码的极少数字排同桶末尾
    # 一级 self (骨架聚族) + 二级 <BASE> + 四级 <U0021> ('!'):
    # 两级都借基表低权符号, 保证列上 汉字 < 数值槽 (位置机制前提).
    # 必须引 collating-symbol (<BASE> = あ 行二级, 值 02), 不能引字符
    # token: 字符作权重 = 元素值的新分配 (实测 <U3042> 被分到 e4 9d 99
    # 高位并搅乱整个值域). 影子层须与四级同构 (骨架列低权 + 槽列按值),
    # 否则位置分区在二级被值序吃掉 (篇十=[十] vs 一篇=[一] ⇒ 1<10 翻转).
    # 权重序 基表符号 < reorder 块新符号 ⇒ 两级列上 汉字 < 数值槽.
    # zhbase 独立使用时一级分出一切, 二/四级仅在全部 tie 时参与
    return (s, rad, cj, v, f'{u(ch)} {u(ch)};<BASE>;IGNORE;<U0021>')

# 汉字单块: 块内 笔画/部首/仓颉/码点. zhnum 不自含汉字行 — 整体 copy zhbase 继承此块
all_rows = sorted(hanzi_row(v, s) for v, s in strokes.items())

# ---- 脚本行 (中文连块): 基表非空一级元素提升到汉字块之上 ----
# iso14651_t1_common 的脚本字符 (假名/希腊/西里尔/谚文/阿拉伯/天城/全角
# 拉丁/数学字母/…, 含补全平面 7-8 位十六进制 token — 统计正则须 {4,8},
# {4,6} 会漏 9292 行) 一级非空且在基表值域 ⇒ 夹在槽键(01 eX)与汉字块
# (ec…)之间, 切断中文区 (实测 万.txt < あ.txt < 章.txt). 修法 = 块内汉字行
# **之后**追加同名行: 一级 self、其余 IGNORE — reorder 块内发射序决定一级
# 值域 ⇒ 汉字 < 兼容汉字 < 其他脚本; 脚本间顺序 = 基表文件序 (iso 组内
# 意图保留: あ/ア 相邻、全角 Ａ 跟 a). **兼容汉字** (F900-FAFF /
# 2F800-2FA1F) 紧跟汉字块、先于其他脚本 ⇒ 中文区 = 汉字块 + 兼容汉字
# 尾巴 (基表未收录的码点由下方区段枚举补齐). ASCII 字母数字排除 (zhnum 里
# 是槽/拉丁行; zhbase 里保持基表位置 = 拉丁在汉字之下). 与汉字块零重叠 (基表不定义 4E00-9FFF), 无塌缩
# 风险; '!'(U0021) 等标点一级 IGNORE 不入集 ⇒ 汉字行四级标记 <U0021>
# 不受影响. 未定义码点 (ext-A/B 汉字等) glibc 回落 = 一~三级 IGNORE +
# 四级固定值, 互相 tie 按邻居排 (实测 㐀 与 𠀀 键相同).
# 注意: 一级字段正则用 [^;]* — \S 含分号会把整行权重串吞进 group,
# IGNORE 行漏判 (实测 8265 个透明元素被误提升).
_w_row = re.compile(r'^<(U[0-9A-F]{4,8})> ([^;]*);')
compat_rows, script_rows = [], []
_compat_cp = set()      # 基表已收录的兼容汉字码点
_seen_tok = set()
_in_tbl = False
for line in open(ISO_FILE, encoding='utf-8'):
    if line.startswith('order_start'):
        _in_tbl = True
        continue
    if not _in_tbl:
        continue
    m = _w_row.match(line)
    if not m or m.group(2) == 'IGNORE':
        continue
    cp = int(m.group(1)[1:], 16)
    if 0x30 <= cp <= 0x39 or 0x41 <= cp <= 0x5A or 0x61 <= cp <= 0x7A:
        continue
    tok = f'<{m.group(1)}>'
    if tok in _seen_tok:
        continue
    _seen_tok.add(tok)
    row = f'{tok} {tok};IGNORE;IGNORE;IGNORE'
    if 0xF900 <= cp <= 0xFAFF or 0x2F800 <= cp <= 0x2FA1F:
        compat_rows.append(row)
        _compat_cp.add(cp)
    else:
        script_rows.append(row)

# 兼容汉字补齐: 基表未收录的码点 (Unicode 后期新增的兼容汉字, 如 U+FA6E/
# U+FA6F/U+FADA..U+FAFF, 以及 2F800 段的两点) 在基表里既无单字行也无区间
# 行 ⇒ glibc 回落到"一~三级 IGNORE", 会排到整个排序的最前面 (连拉丁都在其
# 后), 违反"兼容汉字紧跟汉字块"的契约. 这里按码点补齐, 使其落回兼容汉字尾
# 巴. 按区段枚举而非查 Unihan 表: 兼容汉字区是 Unicode 固定区段, 后续版本只
# 会在区内新增码点 ⇒ 对 Unihan/Unicode 更新天然免疫, 无需额外的数据文件.
# 注意: 其中 40 个码点 (U+FA6E/FA6F/U+FADA..U+FAFF) 不在 glibc 的 UTF-8
# charmap 里, 需配合 gen-charmap.py 生成的补齐版 charmap 才生效 (否则本行被
# localedef 静默丢弃, 字符回落排到最前).
for _cp in list(range(0xF900, 0xFB00)) + list(range(0x2F800, 0x2FA1E)):
    if _cp not in _compat_cp:
        compat_rows.append(f'<U{_cp:04X}> <U{_cp:04X}>;IGNORE;IGNORE;IGNORE')

# ---- 数字区 (仅 zhnum) ----
elems = []              # (元素符号, 定义串)
elem_seen = set()
slots = []              # (值, [写法...]); 同值槽发射前归并
lines = []              # reorder 块内权重行
seen_tok = {}           # 首列 token 去重 (同元素双行 ⇒ 权重塌缩)

ELEM_TEXT = {}          # 符号名 → 原拼写 (slot-order.tsv 基准)

def elem(s):
    """把字符串 s 绑定为多字符 collating-element, 返回符号名(幂等)"""
    sym = 'zh-' + ''.join(str(ord(c)) for c in s)
    if sym not in elem_seen:
        elem_seen.add(sym)
        elems.append((sym, ''.join(u(c) for c in s)))
        ELEM_TEXT[sym] = s
    return sym

def E(*strs):
    return [elem(s) for s in strs]

def add(val, spellings):
    slots.append((val, spellings))

def tok_of(sp):
    return u(sp) if len(sp) <= 1 else f'<{sp}>'

# 0..9: 零/〇 同槽; 大写壹..玖 同槽. 阿拉伯数字不注册 — strxfrm 路径走
# 脚本行自然位, GLib 路径 ASCII 数字段由 GLib 自编码 (自然序, 与 locale 无关)
add(0, ['零', '〇'])
for i, d in enumerate(D, 1):
    add(i, [d, FIN[d], FIN_T[d]])
# 两 = 2 (同值组尾: 二 < 贰 < 两); 十/百/千 系数一处全形有序注册,
#   组内序 = 分财务数字和财务单位, 非财务一堆、财务一堆、混搭一堆,
#   简体在前; ∅ 财务形 拾/佰/仟 居财务堆中, 壹十 之后、壹拾 之前:
#   十 < 一十 < 壹十 < 拾 < 壹拾 < 一拾
add(10, ['十'] + E('一十') + E('壹十') + ['拾'] + E('壹拾') + E('一拾'))
add(100, ['百'] + E('一百') + E('壹百') + ['佰'] + E('壹佰') + E('一佰'))
add(1000, ['千'] + E('一千') + E('壹千') + ['仟'] + E('壹仟') + E('一仟'))

# 系数读法 (值 2..9999): 数字 2..9、十、X十、一百、X百、一千、X千、整十带百
def hundreds(v):
    """110..990 整十带百读法; 110 → 一百一十"""
    h, rest = divmod(v, 100)
    out = ('一' if h == 1 else D[h-1]) + '百'
    if rest:
        t, o = divmod(rest, 10)
        if t: out += ('一' if t == 1 else D[t-1]) + '十'
        if o: out += D[o-1]
    return out
HUND = {v: hundreds(v) for v in range(110, 1000, 10) if v % 100}
COEFS = ([(d, FIN[d], i) for i, d in enumerate(D, 1) if i >= 2]          # 二..九
         + [(d, FIN_T[d], i) for i, d in enumerate(D, 1) if i >= 2]
         + [('十', '拾', 10)]
         + [(d + '十', FIN[d] + '拾', 10 * i) for i, d in enumerate(D[1:], 2)]
         + [(d + '十', FIN_T[d] + '拾', 10 * i) for i, d in enumerate(D[1:], 2)]
         + [('一百', '壹佰', 100)]
         + [(d + '百', FIN[d] + '佰', 100 * i) for i, d in enumerate(D[1:], 2)]
         + [(d + '百', FIN_T[d] + '佰', 100 * i) for i, d in enumerate(D[1:], 2)]
         + [('一千', '壹仟', 1000)]
         + [(d + '千', FIN[d] + '仟', 1000 * i) for i, d in enumerate(D[1:], 2)]
         + [(d + '千', FIN_T[d] + '仟', 1000 * i) for i, d in enumerate(D[1:], 2)]
         + [(HUND[v], HUND[v].translate(TR), v) for v in sorted(HUND)]
         + [(HUND[v], HUND[v].translate(TR_T), v) for v in sorted(HUND)
            if HUND[v].translate(TR_T) != HUND[v].translate(TR)])
# 两位数系数 11..99: 无 '九十九' 元素时 glibc 贪心把 九十九万 切成
# [九十][九万] — 首原子 90 < 100 的槽权重 ⇒ 999999 < 一百 跨位数错序.
# 注册后 九十九万 整体匹配. t=1 两种写法 (十一/一十一) 各成条目,
# ×单位循环与值归并自动等值.
TWO = []
for t in range(1, 10):
    for o in range(1, 10):
        v = t * 10 + o
        stem = (D[t-1] if t > 1 else '') + '十'
        forms = [stem + D[o-1]] + (['一十' + D[o-1]] if t == 1 else [])
        for f in forms:
            TWO.append((f, f.translate(TR), v))
            t2 = f.translate(TR_T)
            if t2 != f.translate(TR):            # 贰叁陆 外同形, 去重防双权重行
                TWO.append((f, t2, v))
COEFS += TWO
# 十/百/千 全形有序注册: 万/亿 链注册数字×单位全部组合 (二万/贰萬/贰万/二萬),
# 十/百/千 系数补全矩阵缺角, 组内序按 "分财务数字和财务单位, 非财务一堆,
# 财务一堆, 混搭一堆, 简体在前":
#   二十 < 贰十 < 贰拾 < 貳拾 < 二拾 < 貳十
# 即 X+U < FIN[X]+U < FIN[X]+FIN[U] < FIN_T[X]+FIN[U] < X+FIN[U] < FIN_T[X]+U
# (FIN_T==FIN 的数字同形自动合并). 混搭形与纯对**交错**注册 ⇒ 本块在独立
# 原子循环之前 (首现定序; 循环对纯对的重复注册由 emit 按 token 去重).
# X=一 组 (壹十 = FIN[一]+U) 已在系数一处全形注册, 此处 X∈二..九.
# 不补: 两佰/两仟 (两 只入数值区与 两X 形), 混搭×万/亿 乘积 (二仟万, 错拼
# 同类), TWO/HUND 部分翻译形 (十玖/二百伍拾, 同属错拼).
for _us, _uf, _uv in (('十', '拾', 10), ('百', '佰', 100), ('千', '仟', 1000)):
    for _i, _d in enumerate(D[1:], 2):
        _forms = [_d + _us, FIN[_d] + _us, FIN[_d] + _uf,
                  FIN_T[_d] + _uf, _d + _uf, FIN_T[_d] + _us]
        add(_i * _uv, [elem(s) for s in dict.fromkeys(_forms)])
# 独立原子: X十/X百/X千/整十带百 (二百人/三千章 等短语首段; 十/百/千 纯对
# 已在上块交错注册, 此处的重复注册被 emit 去重 — 本循环承载 HUND/TWO 纯对)
for r, f, v in COEFS:
    if len(r) >= 2 and r not in ('一百', '一千'):
        add(v, [elem(r), elem(f)])
# 系数拼写矩阵补全: COEFS 只给"规则"系数 (二..九/十/X十/百/X百/千/X千/
# 整十带百) 建槽, 其余复合系数 (一百零一 / 一千二百三十四 类) 无独立槽 —
# 退化多原子后首原子只到系数首段, 而首原子带字形序 (简 < A < 纯财 < B) 且
# 与数值同层比较 ⇒ 前缀写法压过后缀数值 (壹仟零壹拾壹 被当成 壹仟 参与比较,
# 排到 一千零一十 之前). 每个系数单原子后值序直接正确.
# 四形口径同正文: 纯简 / 纯财 / A 数字财+单位简 / B 数字简+单位财; 财务字
# 另含 贰/貳 叁/參 陆/陸 三对异形, 一并注册 (同值相邻不等值).
# 单字形 (一..九/十/百/千) 已在上文注册, 此处只收多字形.
for _bv in range(1, 10000):
    _bs = read(_bv)
    _bm = [f for f in alias_closure(_bs) if len(f) >= 2]
    if _bm:
        add(_bv, [elem(f) for f in _bm])

# 整十元素补 两 形: 两百一十..两百九十 (9 元素). 无它时 两百一十 贪心落
# [两百一](口语 210)+[十], 尾缀是单位权 (十), 大于一切数字权 (九) ⇒
# 两百一十(210) 排到 二百一十九(219) 之后. 注册整十 两 形后 [两百一十]
# 单原子, 尾缀回到数字权, 与 二 侧 [二百一十]+数字 同构.
# 组内序: 同值组尾 (两X/口语形先例 — 注册在财务形之后).
for _v in sorted(HUND):
    if HUND[_v].startswith('二百'):
        add(_v, [elem('两百' + HUND[_v][2:])])
# 单位链: 万(1e4) 亿(1e8) 万亿(1e12) 亿亿(1e16) … 万亿亿亿亿(1e36)
BIG = [('万亿', 12), ('亿亿', 16), ('万亿亿', 20), ('亿亿亿', 24),
       ('万亿亿亿', 28), ('亿亿亿亿', 32), ('万亿亿亿亿', 36)]
UNIT_CHAIN = [('万', '萬', 10**4), ('亿', '億', 10**8)] + \
             [(t, t.translate(str.maketrans('万亿', '萬億')), 10**e) for t, e in BIG]
# COEFS 按 reg 系数归并 (FIN 行与 FIN_T 行分散同 coef; COEFS 序 FIN 前 FIN_T 后
# ⇒ _fins = [简体大写, (繁体财务)]), 供链乘积按层序交错注册
_by_coef = {}
for _r, _f, _v in COEFS:
    _by_coef.setdefault(_r, (_v, []))[1].append(_f)
for unit, fin, val in UNIT_CHAIN:
    # 基础注册 (单位原子/系数乘积/COEFS/口语/省零/带零化合物) 全档共用 —
    # 砍基础会破坏界外值序 (九万亿 vs 一亿: 拆链首原子 9 压不过界内原子).
    # 档位只控制全量枚举 r×u (完美范围主体: r ≤ TIER//u 的非 COEFS 系数,
    # 如 一百零一万). 单位单写 与 一+单位 同槽等值 (万 = 一万, 万亿 = 一万亿);
    # 多字符单位(万亿/亿亿/…)必须注册为元素, 否则被拆成 [万][亿] 逐字比较
    ut = unit if len(unit) == 1 else elem(unit)
    ft = fin if len(fin) == 1 else elem(fin)
    # 组内序同系数类 (∅ 财务形 萬/億 居财务堆中, 壹万 之后、壹萬 之前):
    #   万 < 一万 < 壹万 < 萬 < 壹萬 < 一萬
    add(val, [ut] + E('一' + unit) + E('壹' + unit) + [ft] + E('壹' + fin)
             + E('一' + fin))
    # 系数 × 单位: 二万/二十万/一百万/HUND×万 … ×全部单位 (含 BIG 链).
    # 财务合法四形, 系数词整体作"数字"译财 (不是逐字译 — 壹百万 逐字拆链
    #   [壹百][万] 排 一百一 前), 组内序:
    #   coef+unit < coef_fin+unit < coef_fin+fin < coef_fint+fin < coef+fin
    #   一百万 < 壹佰万 < 壹佰萬 < 貳佰萬 < 一百萬
    # 删形 (类内混错拼): coef_fint+unit (貳佰万: 佰财+万简), 逐字译形
    #   (壹百万/一佰万 拆链或单位混).
    # 裸 '十' 系数特例: _fins[0]=拾 ⇒ A 拾万 / 纯财 拾萬 / B 十萬.
    for _r, (_v, _fins) in _by_coef.items():
        add(_v * val, [elem(s) for s in alias_closure(_r + unit)])
    # 省"一"简写 (百万/千万/千亿) 不注册 — [百][亿] 首原子 100 夹在系数层

def _liang_closure(s, guards=True):
    """s 的全部 两 替换子集 (二 后跟 百千万亿, 每处独立).
    语法守卫: 两不跟十 — 二 的前一字是 十 的替换位不换 (否则产出
    十两万/二十两万 类非法形; 两十 产不出: 替换位后一字恒为单位).
    语法守卫: 零后不接两 — 前一字是 零 的替换位也不换 (一百零两万 类
    非法形).
    guards=False = 裸幂集 — 供截断枚举用: 省零会删掉 二 前面的 零, 源
    上下文守卫会误杀合法终形 (二万零二百九十 → 二万两百九 合法), 合法性
    改由调用点对终形过滤 ('十两'/'零两' 子串)."""
    _pos = [i for i, c in enumerate(s)
            if c == '二' and i + 1 < len(s) and s[i+1] in '百千万亿'
            and not (guards and i and s[i-1] in '十零')]
    _out = set()
    for _mask in range(1 << len(_pos)):
        _t = list(s)
        for _j, _i in enumerate(_pos):
            if _mask >> _j & 1:
                _t[_i] = '两'
        _out.add(''.join(_t))
    return _out

# ---- 全量枚举 r×u (档位 ≥ 单位 u: r ≤ TIER//u, 1..9999) ----
# 完美范围的主体: 非 COEFS 读法 (一百零一/一千二百三十四…) × 单位的化合
# 物单原子化 — 多原子 [一百][零][一][万] 逐位槽权无法表达 1010000 跨值.
# 形态: canonical+unit、财务+财务单位 (混搭交叉不枚举, 同混搭错拼口径).
# TIER=0 不枚举. 化合物补 两 闭包: 两百万 = [两百][万] 拆链 (200,10000)
# 排在 二百一十(210) 前; 一千两百三十四万 拆 [一千两百][三十四][万] 值序
# 全毁. canonical 先, 变体按 (两 个数, 字串).
if TIER:
    for _eu, _efu, _ev in (('万', '萬', 10**4), ('亿', '億', 10**8),
                           ('万亿', '萬億', 10**12)):
        if _ev > TIER:
            continue
        _rmax = min(9999, TIER // _ev)
        for _r in range(1, _rmax + 1):
            _s = read(_r)
            _fs = alias_closure(_s + _eu)
            add(_r * _ev, [elem(f) for f in _fs])
            # 闭包在 化合物 read(r)+u 上 (非 read(r)): r 末位 二 拼上
            # 单位才可换 (一千零两万); 序同省零/带零化合物的 两 闭包
            for _lv in sorted(
                    _liang_closure(_s + _eu) - {_s + _eu},
                    key=lambda f: (f.count('两'), f)):
                add(_r * _ev, [elem(_lv)])

# ---- 两 + 口语省十式 ----
# 序数词无"两"、两只用于量词; 无"两十"; 口语只收三字形
# A百B/A千B/A万B/A亿B = A*U + B*U/10 (二百五/三千六/五万一/两亿五 之类).
# 注册在全部系数×单位之后 ⇒ 同值组内 口语形排最尾 (二百五十 < 贰佰伍拾
# < 二百五); 两在 D 系数之后 ⇒ 二千一 < 两千一. 贪心副作用 (实测无害):
# 标准读法 X U B千 类被 3 字元素抢前缀 (一万一千 = [一万一][千]) —
# 首原子 = 真实前两位数值, 单调 ⇒ 排序保持.
LIANG = '两'
add(2, [LIANG])                                   # 两 = 2 (同值组尾: 二 < 贰 < 两)
# 两X 截断形: 出档也保留 — 撤销后 [两][X] 多原子, 首原子 2 压不过界内
# 单位原子, 破坏档内序
for _u, _uv in (('百', 100), ('千', 1000), ('万', 10**4), ('亿', 10**8)):
    add(2 * _uv, [elem(LIANG + _u)])
for _u, _e in BIG:                                # 3 字化合物单位: 万亿/亿亿
    if len(LIANG + _u) <= 3:
        add(2 * 10**_e, [elem(LIANG + _u)])
# 口语三字 A百B/A千B/A万B: 亿级 (A亿B) 不注册 — 贪心匹配会把它抢成
# [一亿二](1.2e8)[千万] 的首原子, 而同值的规范读法 一亿两千万 走
# [一亿][两千万], 两条链首原子不同 ⇒ 一亿两千万零一(120010000) 会排到
# 二千万九千九百九十九(120009999) 之前. 万级同形抢前缀抢到的是真实前
# 导值、单调无害; 亿级破坏值序. 代价: 一亿二 等 ~90 个口语串退回
# [一亿][二] 多原子.
for _a in list(D) + [LIANG]:
    _av = 2 if _a == LIANG else D.index(_a) + 1
    for _u, _uv in (('百', 100), ('千', 1000), ('万', 10**4)):
        for _b in D:
            _bv = D.index(_b) + 1
            add(_av * _uv + _bv * (_uv // 10),
                [elem(x) for x in alias_closure(_a + _u + _b)])

# ---- 省零化合物 X万B十/X万B百/X千B十/X千B百 = X·U + B·T ----
# 一万一=11000/一万一十=10010/一万一百=10100: 省零读法须单原子 —
# [一万][零][一十] 多原子的跨原子加法语义在逐原子槽权上不可表达.
# 两 闭包: X 位置 (两万二百) + B 位置 (X万两百); canonical 先, 变体按
# (两 个数, 字串) — 二形在前 (组内序). 财务合法四形 (纯简 二万三百 /
# 纯财务 贰萬叁佰 / A 贰千叁百 / B 二仟三佰 / 纯财繁 貳仟參佰).
# X∈一..九, B∈一..九.
for _x in D:
    _xv = D.index(_x) + 1
    for _u2, _uv2 in (('万', 10**4), ('千', 1000)):
        for _t2, _tv2 in (('十', 10), ('百', 100)):
            for _b2 in D:
                _bv2 = D.index(_b2) + 1
                _v2 = _xv * _uv2 + _bv2 * _tv2
                _c1 = _x + _u2 + _b2 + _t2
                _c1s = [_c1] + sorted(_liang_closure(_c1) - {_c1},
                                      key=lambda f: (f.count('两'), f))
                _f2s = alias_closure(_c1)
                add(_v2, [elem(s) for s in
                          _c1s + [f for f in dict.fromkeys(_f2s) if f not in _c1s]])

# ---- 带零读法 X万零T / X千零T ----
# 一万零一百 = [一万][零][一百] 多原子, 首原子 10000 < 10010 恒成立 ⇒ 与
# 单原子 一万一十 的跨原子加法语义不可表达 — 注册带零读法为元素, 单原子
# 值序直接正确. 范围与省零化合物同口径: X万零B十/X万零B百 + X千零B十
# (X∈一..九, B∈一..九); 其余带零形留多原子 — 不追全量 (X万零T T∈1..999
# 需 ~2 万元素). 财务形与 canonical 同值须单原子, 否则 贰万零三百(50300)
# > 五万一十(50010) 类错序. 千级 X千零B百 不注册 (X·1000+B·100 覆盖数
# 亿级, 与省零化合物同截断 — 防元素爆炸).
for _x in D:
    _xv = D.index(_x) + 1
    for _u3, _uv3 in (('万', 10**4), ('千', 1000)):
        for _t3, _tv3 in (('十', 10), ('百', 100)):
            if _u3 == '千' and _t3 == '百':
                continue
            for _b3 in D:
                _bv3 = D.index(_b3) + 1
                _v3 = _xv * _uv3 + _bv3 * _tv3
                _c2 = _x + _u3 + '零' + _b3 + _t3
                _forms = [_c2] + sorted(_liang_closure(_c2) - {_c2},
                                        key=lambda f: (f.count('两'), f))
                _forms += alias_closure(_c2)
                add(_v3, [elem(f) for f in dict.fromkeys(_forms)])

# ---- 截断枚举: 口语截断形单原子化 (v ≡ 0 mod 10, v ≤ 99990) ----
# 四万五千六(45600) 未注册时按 [四万五][千][六] 拆, 尾数字 六(6) 顶不上
# 隐含的 600 ⇒ 排到 四万五千五百(45500) 之前. 注册截断原子后值序直接
# 正确, 且贪心让 canonical 读法抢到更长前缀 (四万五千六百一十 =
# [四万五千六][百][一十] 首原子 45600) — 同完整枚举的前缀关键点效果,
# 元素数 ~1/5 (只枚 v≡0 mod 10).
# 形态: 两 闭包先行, 再截断 — 对 read(v) 的全部 两 替换子集各自去尾
# 单位得 T0, 再去 零 得 TZ. 先闭包后截断的原因: 截断会丢掉尾单位,
# 二万二千 → 二万二 的尾 二 失去后随 千, 换不了 — 混两拼写
# 一万两千一百(12100) 便无 [一万两] 锚点, 落回 [一万][两千] 拆链
# (10000,2000) 排到 一万一千一百(11100) 前. 闭包先行则 read(12100)=
# 一万二千 → {一万二千, 一万两千} → 截断 → {一万二, 一万两} 双锚点.
# 有效性: v%10⁴≠0 (节末单位不可截), 末位数字前是 零 的不截 (二万零九十
# → 二万零九 撞 20009 正规读法), 与已注册拼写同串自动去重 (二百五 已在).
# 裸闭包 + 终形过滤: 省零分支会删掉 二 前面的 零, 源上下文守卫 (前一字
# 是 零 不换) 会误杀合法终形 — 二万零二百九十 的省零形 二万两百九 合法.
# 合法性只看终形: 一万零两百九 (终形含 零两) 在此滤除; 十两 终形产不出
# (替换位前一字 ∈ 起始/千/百/万/零, 省零/截断不会把前字变成 十).
# 确定性: 闭包是 set (hash 序) — 排序后消费, 生成结果与 PYTHONHASHSEED
# 无关; 序 = (两 个数, 字串).
for _v in range(10, TRUNC_LIMIT + 1, 10):
    if _v % 10000 == 0:
        continue
    _r = read(_v)
    if len(_r) < 2 or _r[-1] not in '十百千万亿':
        continue
    if _r[-2] not in D:
        continue
    if len(_r) >= 3 and _r[-3] == '零':
        continue
    _forms = []
    for _full in sorted(_liang_closure(_r, guards=False),
                        key=lambda f: (f.count('两'), f)):
        _t0 = _full[:-1]
        for _f in dict.fromkeys([_t0, _t0.replace('零', '')]):
            if (_f and any(_c in _f for _c in '十百千万亿')
                    and '十两' not in _f and '零两' not in _f):
                _forms.append(_f)
    add(_v, [elem(x) for x in dict.fromkeys(
        f for _f in _forms for f in alias_closure(_f))])

# 序数括号组: (上/前) < (中) < (下/后), 槽值 0.1/0.2/0.3 落在 零 与 一
# 之间; 全角/半角、圆/方括号同槽
LB, RB = ['（', '(', '[', '【'], ['）', ')', ']', '】']
for i, group in enumerate([('上', '前'), ('中',), ('下', '后')]):
    add(0.1 + i * 0.1, [elem(lb + c + rb) for c in group for lb in LB for rb in RB])

# 同值槽归并 (仅分组排序): 同值写法按注册序相邻 (各写法独立槽,
# strcoll ≠ 0)
merged = {}
for val, sps in slots:
    merged.setdefault(val, []).extend(sps)
slots = sorted(merged.items())

# ---- 发射 ----
def emit_lines():
    """发射 reorder 块权重行 — 每写法独立槽: 槽符号按 (值, 注册序) 排列
    ⇒ 同值写法相邻但不等值 (一 < 壹 < 1 < 二). 数值槽四级 + 二级影子:
    借 iso14651 position ⇒ 位置分区; 二级 = 组首 token 影子, 发射序复制
    四级决策 ⇒ GLib 键形 01 eX… 浮到数字段上; 拉丁 a A b B 两级同步
    交错, 三级必须 IGNORE (会打断位置分区). 拉丁一级透明 (GLib 分段后
    纯数字段一级为空, 否则 一.txt < a.txt).
    返回 (权重行, 槽发射序 — slot-order.tsv 基准)."""
    lines, seen, order = [], set(), []
    def w(tok):
        if tok in seen:
            return
        seen.add(tok)
        lines.append(f'{tok} IGNORE;{tok};IGNORE;{tok}')
    for i in range(26):
        lines.append(f'<U{0x61+i:04X}> IGNORE;<U{0x61+i:04X}>;IGNORE;<U{0x61+i:04X}>')
        lines.append(f'<U{0x41+i:04X}> IGNORE;<U{0x41+i:04X}>;IGNORE;<U{0x41+i:04X}>')
    # 每写法独立行 (槽符号 = 自身 token): 符号权重按发射序 ⇒ 值序 + 值内
    # 注册序; 同值写法不等值
    for val, spellings in slots:
        first = None                 # 同值组共享二级影子 (组首 token): 前缀
        for sp in spellings:         # 延伸二级短者在前 ⇒ 拾万 < 十万一;
            tok = tok_of(sp)         # 值≤9 组不共享 — 序数括号后缀须排进
            if tok in seen:          # 同值写法之间 (一（下）< 壹)
                continue
            if first is None:
                first = tok
            if val > 9 and first != tok:
                lines.append(f'{tok} IGNORE;{first};IGNORE;{tok}')
                seen.add(tok)          # 共享行也标记 — 同 token 二次出现勿重发
            else:
                w(tok)
            order.append(sp if len(sp) <= 1 else ELEM_TEXT[sp])
    return lines, order

lines, slot_order = emit_lines()

# ---- 组装 ----
def cat(name):
    return [f'LC_{name}', 'copy "zh_CN"', f'END LC_{name}']

CATEGORIES = ['CTYPE', 'NUMERIC', 'TIME', 'MONETARY', 'MESSAGES', 'PAPER',
              'NAME', 'ADDRESS', 'TELEPHONE', 'MEASUREMENT', 'IDENTIFICATION']

def build(header, copy_src, collate_rows, elems_list):
    file = [*header, *cat('CTYPE'), '']
    for name in CATEGORIES[1:]:
        file += cat(name) + ['']
    file += ['LC_COLLATE', f'copy "{copy_src}"', '']
    file += [f'collating-element <{s}> from "{d}"' for s, d in elems_list]
    file += ['',
             # 锚在 9 后 (新符号字重排在基表全部符号之后, 与锚位无关;
             # zhbase 脚本行在汉字之后 ⇒ 数字区 < 汉字区 < 脚本区)
             'reorder-after <U0039>',
             *collate_rows,
             'reorder-end',
             'END LC_COLLATE',
             '']
    return file

hanzi_rows = [h[4] for h in all_rows] + compat_rows + script_rows
f_zhbase = build(
    ['# zhbase: 默认排序源 — 全部汉字(含数字字)单块,',
     '#   块内 笔画/部首/仓颉/码点; 汉字行后 兼容汉字行 + 脚本行 (基表非空',
     '#   一级元素提升到汉字之上 ⇒ 中文连块 = 汉字块+兼容汉字尾巴+脚本区).',
     '#   被 zhnum 引用的契约:',
     '#   ① 单块结构 + 汉字行后兼容汉字/脚本行  ② 数字字按普通汉字进块 (zhnum 会覆盖)',
     '#   ③ 汉字行二级 <BASE> + 四级 <U0021> (借基表符号, zhnum 位置',
     '#      机制在二/四级的共同前提: 列上 汉字 < 数值槽)',
     '#   ④ 其余类别 copy zh_CN.  换默认排序(如拼音): 重写本文件保持契约.',
     f'# 生成器: gen_zhnum.py: 汉字行 {len(all_rows)}, 兼容汉字行 {len(compat_rows)}, '
     f'脚本行 {len(script_rows)}'],
    'iso14651_t1_common', hanzi_rows, [])
open(OUT_ZHBASE, 'w', encoding='utf-8').write('\n'.join(f_zhbase))

f_zhnum = build(
    ['# zhnum: 拉丁 < 数字(值序) < 汉字(单块默认序) < 其他脚本',
     '# 核心语义: 位置敏感族键 — 同(序数,量词)族聚族且族内纯数值序;',
     '# 同值写法不等值: 相邻但 strcoll ≠ 0 (一 < 壹 < 1 < 二, 第十章 < 第10章).',
     '# 机制: 权重1 骨架聚族 + 数值槽权重4 (借 iso14651 position, 汉字权重4低权);',
     '# 权重2 影子: 槽/拉丁行 = IGNORE;<自身>;IGNORE;<槽>, 汉字行权重2 = <BASE>',
     '# — strxfrm 语义不变 (位置分区在权重2 同构保持), GLib 文件',
     '# 名键形 01 eX… ⇒ 阿拉伯 < 拉丁 < 中文连块 < 其他脚本.',
     '# 默认排序(汉字单块+脚本行)整体引用自 zhbase (copy), 本文件只叠加数值覆盖.',
     f'# 生成器: gen_zhnum.py: 复合元素 {len(elems)}, 数值槽 {len(slots)}, '
     f'数字行 {len(lines)} (无汉字行 — 继承 zhbase {len(all_rows)} 汉字行 '
     f'+ {len(compat_rows)} 兼容汉字 + {len(script_rows)} 脚本行)'],
    'zhbase', lines, elems)
open(OUT_ZHNUM, 'w', encoding='utf-8').write('\n'.join(f_zhnum))

# 副产物: 槽发射序 (verify 同值不等值检查基准)
with open(f'{OUTDIR}/slot-order.tsv', 'w', encoding='utf-8') as f:
    for sp in slot_order:
        f.write(sp + '\n')

print(f'zhbase : 汉字 {len(all_rows)}, 兼容汉字 {len(compat_rows)}, '
      f'脚本 {len(script_rows)}, 共 {len(f_zhbase)} 行')
print(f'zhnum  : 引用 zhbase; 元素 {len(elems)}, 槽 {len(slots)}, '
      f'数字行 {len(lines)}, 共 {len(f_zhnum)} 行 (不含汉字行)')
