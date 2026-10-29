# -*- coding: utf-8 -*-
"""zhnum 读数与写法闭包 —— 生成器与验证脚本共用的纯逻辑。

只做两件事: 把 0..99999999 读成中文数字串 (read), 把一个读数展开成它的全部
合法写法 (alias_closure)。不读数据文件、不写磁盘、不看 argv —— 这些留给
gen_zhnum.py。验证脚本 (alias_spec.py / perf_nau.py) 用正常 import 取用,
不再按注释标记截断源码来 exec。
"""

TRUNC_LIMIT = 99999   # 截断枚举上限: 万级省零截断形 (四万五千六 类) 枚举到 99990

def u(c):
    """码点记号。BMP 用 4 位, 补充平面必须 8 位 —— glibc 基表与 charmap
    都是这么写的 (<U0002F801>); 用 :04X 会把 0x2F801 截成 <U2F801>, 那是
    另一个码点, localedef 静默丢弃该行, 这些兼容汉字回落排到最前。"""
    cp = ord(c)
    return f'<U{cp:04X}>' if cp <= 0xFFFF else f'<U{cp:08X}>'

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


# ── 一个整数的全部合法写法 (契约的唯一实现) ──
# 生成器与检查器都调这里。之前检查器自己实现了一套规则 —— 两份代码实现
# 同一个规则, 规则错了两边一起错, 那才是循环论证。
#
# 写法分三层, 都从规范读法 read(n) 派生:
#   ① 规范读法本身 × 4 种纯风格 (alias_closure)
#   ② 省一: 节首的 "一十" 可省成 "十" (一十万 → 十万, 一万零一十 → 一万零十)
#   ③ 删尾单位: read(n) 去掉末尾的 十/百/千 得到口语形/截断形
#      (二百五十 → 二百五 = 250, 四万五千六百 → 四万五千六 = 45600)
#      仅当删完后仍含单位、且不以 零 开头时合法。

def _drop_tail_unit(s):
    """删末尾单位 (口语形/截断形)。不合法时返回 None。
    规则 (与生成器的口语省十式/截断枚举一致):
      - 末尾必须是 十/百/千
      - 前一个字必须是数字 (不能是 零/单位)
      - 删完仍要有单位, 不能只剩数字
      - 末尾是 十 时, 前一个数字不能是 零 (没有 二百零五 这种省法)
    """
    if len(s) < 2 or s[-1] not in '十百千':
        return None
    if s[-2] not in _DIGS:
        return None
    t = s[:-1]
    if not t or not any(c in _SBKS + _WYS for c in t):
        return None
    # 删完不能是另一个整数的规范读法 —— 一万零一十 删掉 十 得 一万零一,
    # 而那正好是 10001 的读法。一百五十 删得 一百五, 不是任何值的规范读法
    # (150 读作 一百五十), 所以合法。用 read() 反查是最可靠的判据。
    if t[-1] == '零':
        return None
    # 尾单位前面那个数字必须是**该位上的数字**, 不能是个位数字。
    # 判据: 看这个数字前面是不是 零 —— 一万零一十 的 一 前面是 零, 它是
    # 个位数字, 删掉 十 会得到 一万零一 (10001 的读法)。一百五十 的 五
    # 前面是 百 (单位), 它是十位数字, 删掉 十 得 一百五 (150 的口语形)。
    if len(s) >= 3 and s[-3] == '零':
        return None
    return t


def spellings(n, styles='pure'):
    """n 的全部合法写法 —— 契约的唯一实现。

    返回去重后的列表 (顺序 = 注册序, 同值写法按此相邻)。
    """
    base = read(n)
    variants = {base}
    # ② 省一 / 补一 (只适用于节首的 十)
    for i in range(len(base) - 1):
        if base[i] == '一' and base[i + 1] == '十':
            prev = base[i - 1] if i > 0 else None
            if prev is None or prev in '万亿':
                variants.add(base[:i] + base[i + 1:])
    for s in list(variants):
        for i, c in enumerate(s):
            if c != '十':
                continue
            prev = s[i - 1] if i > 0 else None
            if prev is None or prev in '万亿':
                variants.add(s[:i] + '一' + s[i:])
        for i in range(len(s) - 1):
            if s[i] == '零' and s[i + 1] == '十':
                variants.add(s[:i + 1] + '一' + s[i + 1:])
    # ③ 删尾单位 —— 只从**规范读法**删, 不从省一变体删。
    # 一万零一十 的省一形是 一万零十; 若再从它删尾得 一万零一 (那是 10001),
    # 就串值了。删尾只处理 二百五十 → 二百五 这类尾单位可直接省的情形。
    t = _drop_tail_unit(base)
    if t:
        variants.add(t)
    # ④a 省零: 删掉一个 零 (一万零一百 → 一万一百 = 10100, 一千零二十 →
    #     一千二十 = 1020)。守卫:
    #       - 删完不能以 零 开头/结尾, 不能有连续 零
    #       - **零 后面必须还跟着单位**: 一千零一 删零得 一千一, 但 一千一 是
    #         1100 的省写 (一千一百 的省), 不是 1001 ⇒ 不合法。
    #         一万零一百 删零得 一万一百, 一百 有单位 ⇒ 合法。
    for v in list(variants):
        for i, c in enumerate(v):
            if c != '零':
                continue
            rest = v[i + 1:]
            if not rest or not any(u in rest for u in '十百千万亿'):
                continue
            t = v[:i] + rest
            if not t or t[0] == '零' or t[-1] == '零' or '零零' in t:
                continue
            variants.add(t)
    # ④a2 零十 → 零一十 的省一: 一千零一十 → 一千零十 (1010)
    #     与"节首省一"不同, 这是节内零后的 十 也可省 一
    for v in list(variants):
        for i in range(len(v) - 2):
            if v[i] == '零' and v[i+1] == '一' and v[i+2] == '十':
                variants.add(v[:i+1] + v[i+2:])
    # ④ 两 替换: 二 后跟 百/千/万/亿 时可换成 两 (两不跟十)
    #    语法守卫: 两 不跟 十; 零 后不接 两 (一百零两万 非法)
    #    迭代到不动点 —— 两千两 (2200) 需要两次替换:
    #    二千二百 → 两千二百 → 两千两。
    liang = set()
    _work = set(variants)
    while True:
        _new = set()
        for v in _work:
            pos = [i for i, c in enumerate(v)
                   if c == '二' and i + 1 < len(v) and v[i + 1] in '百千万亿'
                   and not (i > 0 and v[i - 1] in '十零')]
            if v.endswith('二百') and len(v) > 2:
                _new.add(v[:-2] + '两')
            if v.endswith('二千') and len(v) > 2:
                _new.add(v[:-2] + '两')
            for mask in range(1 << len(pos)):
                t = list(v)
                for j, i in enumerate(pos):
                    if mask >> j & 1:
                        t[i] = '两'
                _new.add(''.join(t))
        _new -= _work
        if not _new:
            break
        liang |= _new
        _work |= _new
    # ④b 两 本身 = 2 (数量词, 不参与 二 的替换规则)
    if n == 2:
        liang.add('两')
    # ⑤ 单位独用形: 十/百/千 可单写 (百 = 一百), 万/亿 亦然
    units = set()
    for v in list(variants) + list(liang):
        if v == '一百':
            units.update(['百', '佰'])
        elif v == '一千':
            units.update(['千', '仟'])
        elif v == '一十':
            units.update(['十', '拾'])
        elif v == '一万':
            units.update(['万', '萬'])
        elif v == '一亿':
            units.update(['亿', '億'])
    # × 4 种纯风格
    out = []
    for v in sorted(variants | liang | units):
        out.extend(alias_closure(v, styles))
    # 两 本身 (值 2) 与 两X 的财务/繁体形不走 alias_closure (两 不在 _DIGS)
    out.extend(sorted(liang))
    return list(dict.fromkeys(out))
