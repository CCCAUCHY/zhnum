#!/usr/bin/env python3
"""生成 zhbase + zhnum locale 源文件.

zhnum 的 LC_COLLATE 通过 copy "zhbase" 引用默认排序 (换默认排序只改
zhbase, zhnum 自动跟随):

  zhbase — 默认排序源. 全部汉字(含数字字)单块: 块内 笔画数 kTotalStrokes
      → 部首 kRSUnicode → 仓颉 kCangjie → 码点; 汉字行后追加脚本行
      (基表非空一级元素整体提升, 中文连块). 汉字以 Unihan 为准, 基表
      只提供其他文字, 它附带的兼容汉字不参与设计. 被 zhnum 引用的契约:
      ① 单块结构 + 汉字行后脚本行  ② 数字字按普通汉字进块
      (zhnum 用数值槽覆盖)  ③ 汉字行二级 <BASE> + 四级 <U0021> (借基表
      符号 — zhnum 位置机制的前提, 见下)  ④ 其余 LC 类别 copy zh_CN.
  zhnum  — copy "zhbase" + 单 reorder 块叠加数值覆盖 (无汉字行):
      首字序 = 拉丁 < 数字(值序) < 汉字(单块默认序) < 其他脚本
      (GLib 文件名路径: 阿拉伯 < 拉丁 < 中文连块 < 其他脚本).

      核心语义: 位置敏感族键 — N篇 (量词=篇, 序数标记=空) 与 篇N (序数
      标记=篇, 量词=空) 是不同族, 不混排; 同(序数标记,量词)族聚族 (含空),
      族内纯数值序。同值写法因各占一槽而落在同一段、彼此不等值 —— 这是
      机制的副产品, 不是单独维护的目标; 它们之间的先后不保证
      (实际按注册序: 一 < 壹 < 1 < 二, 第十章 < 第10章)。

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
    sys.exit('用法: python3 gen_zhnum.py TIER OUTDIR\n'
             '  TIER  完美范围上限 10**n (0 = 不枚举)\n'
             '  OUTDIR 输出目录\n'
             '只注册全小写/全大写两套写法 (各带简繁)。混搭写法 (小写数字+大写单位\n'
             '之类) 不是实际书写习惯, 语料里几乎不出现, 且实测有跨风格错序、\n'
             '编译还更慢 (亿-mixed 比 亿亿-pure 还久) —— 已整体废弃。')
TIER = int(sys.argv[1])
OUTDIR = sys.argv[2]
STYLES = 'pure'
from zhnum_core import (TRUNC_LIMIT, read, u,
                        D, FIN, FIN_T, TR, TR_T,
                        alias_closure as _alias_closure)

def alias_closure(s):
    """写法闭包 (只出全小写/全大写两套, 各带简繁 —— 混搭已废弃)"""
    return _alias_closure(s, STYLES)


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
# 值域 ⇒ 汉字 < 其他脚本; 脚本间顺序 = 基表文件序 (iso 组内意图保留:
# あ/ア 相邻、全角 Ａ 跟 a). ASCII 字母数字排除 (zhnum 里是槽/拉丁行;
# zhbase 里保持基表位置 = 拉丁在汉字之下). 与汉字块零重叠 (基表不定义
# 4E00-9FFF), 无塌缩风险; '!'(U0021) 等标点一级 IGNORE 不入集 ⇒ 汉字行
# 四级标记 <U0021> 不受影响. 未定义码点 (ext-A/B 汉字等) glibc 回落 =
# 一~三级 IGNORE + 四级固定值, 互相 tie 按邻居排 (实测 㐀 与 𠀀 键相同).
#
# 基表附带的汉字 (兼容汉字 F900-FAFF / 2F800-2FA1F, 共 1014 行) 一并按
# 脚本行处理: **zhbase 的汉字以 Unihan 为准**, 基表只提供其他文字, 它附带
# 的汉字不参与排序设计 (不进汉字块、不补权重、不按区段补齐)。它们的实际
# 位置由 glibc 的基表回退决定, 不在契约内。
# 注意: 一级字段正则用 [^;]* — \S 含分号会把整行权重串吞进 group,
# IGNORE 行漏判 (实测 8265 个透明元素被误提升).
_w_row = re.compile(r'^<(U[0-9A-F]{4,8})> ([^;]*);')
script_rows = []
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
    script_rows.append(f'{tok} {tok};IGNORE;IGNORE;IGNORE')

# ---- 数字区 (仅 zhnum) ----
elems = []              # (元素符号, 定义串)
elem_seen = set()
slots = []              # (值, [写法...]); 同值槽发射前归并

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
# 两 = 2 (同值组尾: 二 < 贰 < 两)。
# 十/百/千 的写法**只列契约内的**: 纯小写 (十/百/千)、带一 (一十)、
# 全大写 (拾/壹拾/貳拾...)。旧版还列了 壹十 / 一拾 这类大小写混搭 ——
# 混搭非法 (没人简繁混用、财务大小写混搭也不正规), 不在契约内, 不建槽。
# 跨类 (简体 vs 财务 vs 繁体) 的相对顺序不保证, 只保证同类内序。
add(10, ['十'] + E('一十') + ['拾'] + E('壹拾'))
add(100, ['百'] + E('一百') + ['佰'] + E('壹佰'))
add(1000, ['千'] + E('一千') + ['仟'] + E('壹仟'))

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
         + [('十', '拾', 10), ('一十', '壹拾', 10)]
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
# X十/X百/X千 的纯写法由下面的 COEFS 循环经 alias_closure 注册 —— 这里不再
# 手写写法表。旧版列了 6 个形 (二十/贰十/贰拾/貳拾/二拾/貳十), 其中三个是
# 大小写混搭 (贰十/二拾/貳十)。混搭不在契约内 (没人简繁混用、财务大小写
# 混搭也不正规), 为它们建槽并维护组内序纯属复杂度: 同类内序正确、跨类顺序
# 不保证即可, 就像兼容错字。
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
# 另含 贰/貳 叁/參 陆/陸 三对异形, 一并注册 (各占一槽)。
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
    for _eu, _ev in (('万', 10**4), ('亿', 10**8), ('万亿', 10**12)):
        if _ev > TIER:
            continue
        _rmax = min(9999, TIER // _ev)
        for _r in range(1, _rmax + 1):
            _s = read(_r)
            _fs = alias_closure(_s + _eu)
            # 十位是 一 的系数还要收省 一 的形 (一十万 / 壹拾万 / 一十亿):
            # 规范读法是 一十万, 但 十万 同样常见且已作为 [十][万] 注册;
            # 不注册 一十万 会让它退化成 [一十][万] 两原子, 首原子 10 的槽
            # 排在 十一 之前 ⇒ 一十万 排在 十一 之前 (实测逆序).
            if _s.startswith('一十'):
                _fs += alias_closure(_s[1:] + _eu)
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
                # 十位是 一 时还要收省 一 的形 (一万零十 / 一万零壹拾):
                # 规范读法是 一万零一十, 但 一万零十 同样常见, 不注册会退化成
                # [一万][零][十] 三原子, 首原子 10000 让 一万零十一 排到
                # 一万零一十 之前 (实测逆序).
                if _t3 == '十' and _b3 == '一':
                    _short = _x + _u3 + '零十'
                    _forms += [_short] + sorted(_liang_closure(_short) - {_short},
                                                key=lambda f: (f.count('两'), f))
                    _forms += alias_closure(_short)
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
    # 规范读法本身也要注册 —— 旧版只注册截断形 (_t0), 于是 10110 这种
    # 不是 r×u 形式的值只有 一万零一百一 (口语形), 规范读法 一万零一百一十
    # 漏注册, 整串退化成多原子。实测 28.7% 的注册值缺规范读法。
    _forms = [alias_closure(_r)]           # ① 规范读法
    for _full in sorted(_liang_closure(_r, guards=False),
                        key=lambda f: (f.count('两'), f)):
        _t0 = _full[:-1]
        for _f in dict.fromkeys([_t0, _t0.replace('零', '')]):
            if (_f and any(_c in _f for _c in '十百千万亿')
                    and '十两' not in _f and '零两' not in _f):
                _forms.append(alias_closure(_f))   # ② 截断形
    add(_v, [elem(x) for x in dict.fromkeys(f for fs in _forms for f in fs)])

# 序数括号组: (上/前) < (中) < (下/后), 槽值 0.1/0.2/0.3 落在 零 与 一
# 之间; 全角/半角、圆/方括号同槽
LB, RB = ['（', '(', '[', '【'], ['）', ')', ']', '】']
for i, group in enumerate([('上', '前'), ('中',), ('下', '后')]):
    add(0.1 + i * 0.1, [elem(lb + c + rb) for c in group for lb in LB for rb in RB])

# 槽归并: 每个写法各占一槽。同值写法自然落在同一段 (位置由值序决定),
# 彼此不等值也是机制结果 —— 不是为了保证什么额外的东西。
# 写法来源统一为 zhnum_core.spellings() —— 契约的唯一实现。
# 值集合仍由上面的各个块决定 (哪些值值得注册是代价权衡), 但每个值的
# **写法**全部来自 spellings(), 避免"生成器和检查器各实现一套规则"。
# 单字写法用字符 token, 多字才绑 collating-element (否则与 zhbase 冲突)。
from zhnum_core import spellings as _spellings
merged = {}
for val, sps in slots:
    if isinstance(val, int):
        merged.setdefault(val, []).extend(
            (x if len(x) == 1 else elem(x)) for x in _spellings(val))
    else:
        merged.setdefault(val, []).extend(sps)
slots = sorted(merged.items())

# ---- 发射 ----
def emit_lines():
    """发射 reorder 块权重行 — 每写法独立槽: 槽符号按 (值, 注册序) 排列,
    值序因此直接来自槽的发射序。同值写法落在同一段是这一机制的副产品
    (位置由值决定), 不是单独维护的目标。数值槽四级 + 二级影子:
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
    # 每写法独立行 (槽符号 = 自身 token): 符号权重按发射序 ⇒ 值序。
    # 同值写法落在同一段、彼此不等值, 是"各占一槽"的副产品。
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
            order.append((val, sp if len(sp) <= 1 else ELEM_TEXT[sp]))
    return lines, order

lines, slot_order = emit_lines()

# ---- 组装 ----
# 头部与 LC_IDENTIFICATION 照上游 localedata/locales/* 的写法: 先 comment_char/
# escape_char, 再数据声明, 再一句描述; 不写生成器、也不描述本文件引用了谁
# (上游文件里没有这些)。数据声明改写自 glibc 各 locale 文件开头那段 —— 措辞
# 不能照抄: 那句说的是"本文件是 GNU C Library 的一部分", 对我们这份还不成立。
def cat(name):
    if name == 'IDENTIFICATION':
        return ['LC_IDENTIFICATION',
                'title      "Chinese locale with numeric collation"',
                'source     "https:////github.com//CCCAUCHY//zhnum"',
                'address    ""',
                'contact    ""',
                'email      ""',
                'tel        ""',
                'fax        ""',
                'language   "Chinese"',
                'territory  "China"',
                'revision   "1.0"',
                'END LC_IDENTIFICATION']
    return [f'LC_{name}', 'copy "zh_CN"', f'END LC_{name}']

DATA_NOTICE = [
    '% This file contains locale data.',
    '% The copyright holder does not claim any copyright interest in the',
    '% locale data contained in this file.  The foregoing does not affect the',
    '% license of this project as a whole.  It does not exempt you from the',
    '% conditions of the license if your use would otherwise be governed by',
    '% that license.',
    '']

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

hanzi_rows = [h[4] for h in all_rows] + script_rows
f_zhbase = build(
    # 顺序要紧: escape_char 必须先于 comment_char。实测两行都声明时, 顺序写反
    # 会让 localedef 编出的 LC_COLLATE 膨胀 2.4 倍 (28.7 MB → 68.6 MB); 单独
    # 声明任一行都正常。上游 localedata/locales/* 全是 escape_char 在前。
    ['escape_char /',
     'comment_char %',
     '',
     *DATA_NOTICE,
     '% zhbase — collation source for Chinese: all CJK ideographs in one block,',
     '% ordered by stroke count, radical, cangjie code and code point; the',
     '% script ranges follow that block.',
     '',
     '% Ideograph ordering data is derived from the Unihan database',
     '% <https://www.unicode.org/Public/UNIDATA/Unihan.zip>, used under the',
     '% Unicode License v3 (see LICENSE-UNICODE).'],
    'iso14651_t1_common', hanzi_rows, [])
open(OUT_ZHBASE, 'w', encoding='utf-8').write('\n'.join(f_zhbase))

f_zhnum = build(
    # 顺序要紧: escape_char 必须先于 comment_char。实测两行都声明时, 顺序写反
    # 会让 localedef 编出的 LC_COLLATE 膨胀 2.4 倍 (28.7 MB → 68.6 MB); 单独
    # 声明任一行都正常。上游 localedata/locales/* 全是 escape_char 在前。
    ['escape_char /',
     'comment_char %',
     '',
     *DATA_NOTICE,
     '% zhnum — numeric collation for Chinese numerals: a numeral string is',
     '% compared by the number it denotes rather than character by character',
     '% (一 < 二 < 十 < 十一 < 一百 < 一百零一 < 一千).'],
    'zhbase', lines, elems)
open(OUT_ZHNUM, 'w', encoding='utf-8').write('\n'.join(f_zhnum))

# 副产物: 槽发射序 —— 每行 `值<TAB>写法`, 顺序即注册序。
# 这是检查器的**权威来源**: 检查器不该自己推"哪些写法合法", 直接读这里,
# 才能避免"检查器和生成器各读各的" (一十万 的错序就是这样躲过抽样的)。
with open(f'{OUTDIR}/slot-order.tsv', 'w', encoding='utf-8') as f:
    for val, sp in slot_order:
        f.write(f'{val}\t{sp}\n')

print(f'zhbase : 汉字 {len(all_rows)}, '
      f'脚本 {len(script_rows)}, 共 {len(f_zhbase)} 行')
print(f'zhnum  : 引用 zhbase; 元素 {len(elems)}, 槽 {len(slots)}, '
      f'数字行 {len(lines)}, 共 {len(f_zhnum)} 行 (不含汉字行)')
