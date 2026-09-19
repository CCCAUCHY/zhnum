# -*- coding: utf-8 -*-
"""zhnum 读数与写法闭包 —— 生成器与验证脚本共用的纯逻辑。

只做两件事: 把 0..99999999 读成中文数字串 (read), 把一个读数展开成它的全部
合法写法 (alias_closure)。不读数据文件、不写磁盘、不看 argv —— 这些留给
gen_zhnum.py。验证脚本 (alias_spec.py / perf_nau.py) 用正常 import 取用,
不再按注释标记截断源码来 exec。
"""

TRUNC_LIMIT = 99999   # 截断枚举上限: 万级省零截断形 (四万五千六 类) 枚举到 99990

def u(c):
    return f'<U{ord(c):04X}>'

def read(n):
    """0..99999999 canonical 读法 (枚举用, 与 verify.py read 同节式语义)"""
    if n >= 10**8:
        raise ValueError('read 仅支持 <1e8')
    if n == 0: return '零'
    s = str(n); units = ['', '十', '百', '千']
    secs = []
    while s: secs.append(s[-4:]); s = s[:-4]
    sec_units = ['', '万']
    out = ''
    for si in range(len(secs)-1, -1, -1):
        sec = secs[si]; body = ''
        for i, ch in enumerate(sec):
            d = int(ch); pos = len(sec) - 1 - i
            if pos == 0: body += D[d-1] if (d or len(sec) == 1) else ''
            else:
                if d == 0:
                    if body and not body.endswith('零'): body += '零'
                else:
                    if not (d == 1 and pos == 1 and len(sec) == 2 and not body): body += D[d-1]
                    body += units[pos]
        if body and sec[0] == '0': body = '零' + body
        body = body.rstrip('零')
        if body: out += body + (sec_units[si] if si else '')
    return out or '零'

D = '一二三四五六七八九'
# 大写数字双形: 简体大写 + 繁体财务字 (贰/貳 叁/參 陆/陸 三对异形, 其余同形;
# 值内序: 小写 < 简体大写 < 繁体财务 (注册序), 同值同排)
FIN = dict(zip(D, '壹贰叁肆伍陆柒捌玖'))          # 简体大写
FIN_T = dict(zip(D, '壹貳參肆伍陸柒捌玖'))        # 繁体财务
TR = str.maketrans('一二三四五六七八九十百千', '壹贰叁肆伍陆柒捌玖拾佰仟')   # 简体大写
TR_T = str.maketrans('一二三四五六七八九十百千', '壹貳參肆伍陸柒捌玖拾佰仟') # 繁体财务
# 财务合法形: 数字/单位各类内部大小写统一 —
# 合法形 = 纯简 s / 纯财务 TRF_(s) / A=数字财务+单位简体 TRD_(s) / B=数字简体+单位财务 TRU_(s);
# 类内混写 (贰千零三百: 数字混 / 壹千玖佰: 单位混 / 二十萬: 单位混) = 错拼, 一律不注册.
TRF_ = str.maketrans('一二三四五六七八九十百千万', '壹贰叁肆伍陆柒捌玖拾佰仟萬')   # 纯财务 (含万)
TRFT_ = str.maketrans('一二三四五六七八九十百千万', '壹貳參肆伍陸柒捌玖拾佰仟萬')
TRD_ = str.maketrans(D, '壹贰叁肆伍陆柒捌玖')    # A: 只译数字
TRDT_ = str.maketrans(D, '壹貳參肆伍陸柒捌玖')  # A 繁体
TRU_ = str.maketrans('十百千万', '拾佰仟萬')      # B: 只译单位

# 别名闭包: 同一数值的全部中文写法。四种风格 —— 全小写 / 全大写 / 小写数字+
# 大写单位 / 大写数字+小写单位, 每种各带简繁一套。
# 分类: 十百千 前面有数字时属单位类 (一千 的 千), 否则属数字类 (十万 的 十);
#   万亿 恒属单位类。
# 两轴独立: 数字类 小写/大写简/大写繁 (贰/貳 叁/參 陆/陸); 单位类 简繁 是
#   万/萬 亿/億 —— 萬 是繁体字而非财务字, 故简体的全大写是 壹佰万 (人民币
#   壹佰万元整), 繁体的全大写才是 壹佰萬。数字类 3 形 × 单位类 4 形展开即得
#   全部写法, 注册点只写一次闭包 ⇒ 不存在"某别名注册了、另一种漏了"的余地
#   (漏一种写法即整串退化多原子, 首原子的写法序会压过后缀数值)。
_DIGS = '一二三四五六七八九'
_SBKS = '十百千'
_WYS = '万亿'
_DMAP = [str.maketrans('', ''),
         str.maketrans(_DIGS + _SBKS, '壹贰叁肆伍陆柒捌玖' + '拾佰仟'),
         str.maketrans(_DIGS + _SBKS, '壹貳參肆伍陸柒捌玖' + '拾佰仟')]
_UMAP = [str.maketrans('', ''),                          # 小写简
         str.maketrans(_SBKS, '拾佰仟'),                  # 大写简 (万/亿 仍是 万/亿)
         str.maketrans(_WYS, '萬億'),                     # 小写繁
         str.maketrans(_SBKS + _WYS, '拾佰仟' + '萬億')]   # 大写繁
# 风格组合 (数字类风格下标, 单位类风格下标)。
# 纯形 = 数字类与单位类同级配对: 全小写 (小写+小写) 与 全大写 (大写+大写),
#   各带简繁 —— 四种风格里不含混搭的两套。
# 含混搭 = 再加上「小写数字+大写单位」与「大写数字+小写单位」两套。
# 组内序 = 注册序 (同值写法按此相邻): 纯简 < 纯财 < A 数字财+单位简 < B 数字简+
# 单位财 < 繁财; 其余组合排在其后。
_STYLE_PURE = ((0, 0), (1, 1), (0, 2), (2, 3))
_STYLE_MIXED = ((0, 0), (1, 1), (1, 0), (1, 2), (1, 3),
                (0, 1), (0, 2), (0, 3), (2, 1), (2, 3), (2, 0), (2, 2))
# (风格组合的选择在 alias_closure 里按 styles 参数进行)

def _cls(s):
    """逐字符分类: 'd' 数字类 / 'u' 单位类"""
    g, prev_d = [], False
    for c in s:
        if c in _SBKS + _WYS:
            is_u = prev_d or c in _WYS
            g.append('u' if is_u else 'd')
            prev_d = not is_u
        else:
            g.append('d')
            prev_d = c in _DIGS
    return g

def alias_closure(s, styles='mixed'):
    """读数 s 的全部合法写法 (数字类 3 形 × 单位类 4 形, 类内统一)。
    styles: 'mixed' 四种风格全展开; 'pure' 只全小写/全大写两套。"""
    _order = _STYLE_MIXED if styles == 'mixed' else _STYLE_PURE
    g = _cls(s)
    return list(dict.fromkeys(
        ''.join(c.translate(_DMAP[d] if grp == 'd' else _UMAP[u_])
                for c, grp in zip(s, g))
        for d, u_ in _order))

def u(c):
    return f'<U{ord(c):04X}>'
