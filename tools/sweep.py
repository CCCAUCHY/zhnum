# -*- coding: utf-8 -*-
"""sweep.py — 数值序抽样/全量扫描 (只走 GLib 路径, 即 Nautilus 实际用的那条)。

**独立实现**: 本文件自带 整数→中文 的转换, 不 import gen_zhnum.py 或
zhnum_core.py。理由是把基准从"生成器自己的顺序"换成"按语言规则独立推出的
数值" —— 否则只是拿生成器和自己比对 (两次输入同一个密码)。

检查内容 (对每个值, 四种情形各算一遍):
  情形      裸数字.txt / 第X章.txt / 篇X.txt / X篇.txt
  写法      八种: 全小写(简/繁) 全大写(简/繁)
            小写数字+大写单位(简/繁) 大写数字+小写单位(简/繁); 不去重。
  断言      ① 值序: 值 v 的全部写法的排序键, 必须全部大于值 v-1 的全部键
            ② 同值内不等值: 同一值里两个不同的字符串, 键不得相等

流式: 按键不落盘、不留全部语料 —— 只保留"上一值的最大键", 内存 O(1)。
因此可以按值递增直接生成, 不需要先排序, 也不需要把整数集读进内存。

用法:
  python3 tools/sweep.py --tier 亿  --start 0 --count 100000000
  python3 tools/sweep.py --tier 亿亿 --sample 100000000 --seed 7
  python3 tools/sweep.py --tier 亿 --start 0 --count 10100000000 --chunk 1/75
环境: LOCPATH 指向已编译的 locale 目录, LC_ALL=zhnum.UTF-8。
"""
import argparse, ctypes, locale, json, os, random, sys, time
from multiprocessing import Pool

# ─────────────────────────── 独立实现: 整数 → 中文 ───────────────────────────
_D = '一二三四五六七八九'
# 单位类的四种风格 (下标 0/1 = 小写简/大写简, 2/3 = 小写繁/大写繁)
_U = ['十百千万亿', '拾佰仟万亿', '十百千萬億', '拾佰仟萬億']
# 数字类的三种风格 (小写 / 大写简 / 大写繁), 含把 十百千 当数字用时的大写形
_N = [str.maketrans(_D + '十百千', _D + '十百千'),
      str.maketrans(_D + '十百千', '壹贰叁肆伍陆柒捌玖' + '拾佰仟'),
      str.maketrans(_D + '十百千', '壹貳參肆伍陸柒捌玖' + '拾佰仟')]
_UNITS = ('', '十', '百', '千')


def _read4(n):
    """1..9999 的规范读法 (不带万/亿)"""
    out, zero = [], False
    for pos in (3, 2, 1, 0):
        d = (n // 10 ** pos) % 10
        if d == 0:
            if out:
                zero = True
            continue
        if zero:
            out.append('零')
            zero = False
        if not (d == 1 and pos == 1 and not out):      # 十, 不是 一十
            out.append(_D[d - 1])
        out.append(_UNITS[pos])
    return ''.join(out)


def canon(n):
    """0..10^16 的规范中文读法 (小写简), 按语言规则, 与生成器无关"""
    if n == 0:
        return '零'
    if n < 10 ** 4:
        return _read4(n)
    if n < 10 ** 8:
        q, r = divmod(n, 10 ** 4)
        return _read4(q) + '万' if r == 0 else \
            _read4(q) + '万' + (('零' + _read4(r)) if r < 1000 else _read4(r))
    q, r = divmod(n, 10 ** 8)
    return canon(q) + '亿' if r == 0 else \
        canon(q) + '亿' + (('零' + canon(r)) if r < 10 ** 7 else canon(r))


def _cls(s):
    """逐字符分类: 'n' 数字类 / 'u' 单位类。十百千 前面有数字 ⇒ 单位类。"""
    g, prev_d = [], False
    for c in s:
        if c in '十百千万亿':
            is_u = prev_d or c in '万亿'
            g.append('u' if is_u else 'n')
            prev_d = not is_u
        else:
            g.append('n')
            prev_d = c in _D
    return g


# 写法组合 = 数字类风格 × 单位类风格 (不去重)。
# mixed 版注册八种; pure 版只注册"同级配对"的四种 —— 拿八种去查 pure 必然误报,
# 因为混搭写法它本来就没注册 (那是 pure 明示的取舍), 那些串会退化成多原子。
_PURE = ((0, 0), (0, 2), (1, 1), (2, 3))
_MIXED = ((0, 0), (0, 2), (1, 1), (2, 3),
          (0, 1), (0, 3), (1, 0), (2, 2))
_STYLES = _MIXED


def forms(n):
    """n 的八种写法 (原样列出, 不去重)"""
    s = canon(n)
    g = _cls(s)
    out = []
    for d, u in _STYLES:
        tu = str.maketrans('十百千万亿', _U[u])
        out.append(''.join(c.translate(_N[d] if gr == 'n' else tu)
                           for c, gr in zip(s, g)))
    return out


# 四种情形: (前缀, 后缀)
CASES = [('裸数字', '', '.txt'), ('第X章', '第', '章.txt'),
         ('篇X', '篇', '.txt'), ('X篇', '', '篇.txt')]


# ─────────────────────────────── 扫描 ───────────────────────────────
# 两种模式:
#   seq    —— 按值递增直接遍历区间 (全量扫描)。不需要排序、不需要存储: 单调性
#             用「本条全部键 > 上一条最大键」判定, 内存 O(1)。
#   sample —— 先随机取 N 个值并**排序**, 再按同样流程遍历。排序是必须的:
#             随机相邻的两个值之间没有值序关系, 拿它们比较必然误报。
# 两种模式都按位置切片并行; 每个切片多带一条前驱值 (不计数), 好让切片边界的
# 值序也被覆盖 —— 否则每个 worker 的第一条都因 prev=None 被跳过。
import bisect

_VALS = None          # sample 模式的已排序值表 (fork 后由子进程 COW 共享)


def _check_one(key, v, last):
    fs = forms(v)
    for name, pre, suf in CASES:
        ks = [key(pre + f + suf) for f in fs]
        mn, mx = min(ks), max(ks)
        prev = last.get(name)
        if prev is not None and mn <= prev:
            return {'ok': False, 'kind': '值序', 'case': name, 'value': v,
                    'forms': fs, 'keys': [k.hex() for k in ks],
                    'prev_max': prev.hex()}
        for i2 in range(len(fs)):
            for j2 in range(i2 + 1, len(fs)):
                if fs[i2] != fs[j2] and ks[i2] == ks[j2]:
                    return {'ok': False, 'kind': '同值等值', 'case': name,
                            'value': v, 'forms': [fs[i2], fs[j2]],
                            'keys': [ks[i2].hex()]}
        last[name] = mx
    return None


# GLib 的排序键是**字节串**, 但 gi 绑定会按 UTF-8 解码成 str —— 键里出现非
# UTF-8 字节就抛 UnicodeDecodeError (实测 runner 的 Python 3.12 上必炸)。
# 直接用 ctypes 调那个 C 函数拿原始字节, 不经解码; 顺带也去掉了 python3-gi
# 依赖 (libglib 本来就在)。这就是 Nautilus 排序时调用的同一个函数。
_libglib = ctypes.CDLL('libglib-2.0.so.0')
_libglib.g_utf8_collate_key_for_filename.restype = ctypes.c_void_p
_libglib.g_utf8_collate_key_for_filename.argtypes = [ctypes.c_char_p, ctypes.c_ssize_t]
_libglib.g_free.argtypes = [ctypes.c_void_p]


def glib_key(s):
    p = _libglib.g_utf8_collate_key_for_filename(s.encode('utf-8'), -1)
    if not p:
        return b''
    try:
        return ctypes.string_at(p)
    finally:
        _libglib.g_free(p)


def _worker(arg):
    lo, hi, styles = arg
    # 显式接收而不是靠 fork 继承: Python 3.14 在 Linux 上已把 multiprocessing
    # 默认启动方式从 fork 改为 spawn/forkserver —— 子进程会重新 import 模块,
    # 主进程改过的模块级变量传不过去, 静默回落成 import 时的值。
    global _STYLES
    _STYLES = _PURE if styles == 'pure' else _MIXED
    # GLib 的排序走 C 库的 locale 状态 —— 只设 LC_ALL/LOCPATH 环境变量不生效,
    # 必须 setlocale (漏了它 GLib 会静默回落到 C 序, 键退化成字符串本身的字节,
    # 于是任何比较都无意义)。
    locale.setlocale(locale.LC_ALL, '')
    key = glib_key
    last = {}
    n = 0
    t0 = time.time()
    for idx in range(lo, hi):
        v = _VALS[idx] if _VALS is not None else idx
        bad = _check_one(key, v, last)
        if bad:
            bad['n_checked'] = n
            return bad
        n += 1
    return {'ok': True, 'n_checked': n, 'secs': time.time() - t0,
            'rate': n / max(time.time() - t0, 1e-9)}


def _init(vals):
    global _VALS
    _VALS = vals


def main():
    global _VALS
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', required=True, choices=['亿', '万亿', '亿亿'])
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--count', type=int, default=0,
                    help='seq 模式: 从 --start 起扫多少条 (0 = 到 --end 或档位前沿)')
    ap.add_argument('--end', type=int, default=0, help='seq 模式上界 (不含)')
    ap.add_argument('--sample', type=int, default=0,
                    help='sample 模式: 随机取多少条 (先排序再查)')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--chunk', default='', help='切片 i/n  (i 从 0 起)')
    ap.add_argument('--workers', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--styles', default='mixed', choices=['pure', 'mixed'],
                    help='查哪些写法: mixed 八种 (默认), pure 四种')
    ap.add_argument('--report', default='', help='发现错序时把证据写到这个文件')
    a = ap.parse_args()
    global _STYLES
    _STYLES = _PURE if a.styles == 'pure' else _MIXED

    locale.setlocale(locale.LC_ALL, '')
    got = locale.setlocale(locale.LC_ALL)
    if 'zhnum' not in got:
        sys.exit(f'LC_ALL 不是 zhnum (实际 {got!r}) —— 检查 LC_ALL / LOCPATH')
    FRONTIER = {'亿': 101 * 10 ** 8, '万亿': 101 * 10 ** 12, '亿亿': 101 * 10 ** 16}[a.tier]
    hi = min(a.end or FRONTIER, FRONTIER)
    if a.sample:
        n_total = a.sample
        ci, cj = 0, 1                    # 不给 --chunk 就是整份一片
        if a.chunk:
            ci, cj = (int(x) for x in a.chunk.split('/'))
        per = (n_total + cj - 1) // cj
        n_this = max(0, min(per, n_total - ci * per))
        rng = random.Random(a.seed + ci * 7919)
        _VALS = sorted(rng.randrange(a.start, hi) for _ in range(n_this))
        mode, idx_lo, idx_hi = f'sample 切片 {ci}/{cj}', 0, len(_VALS)
    else:
        idx_lo, idx_hi = max(a.start, 0), hi if not a.count else min(hi, a.start + a.count)
        if a.chunk:
            ci, cj = (int(x) for x in a.chunk.split('/'))
            span = (idx_hi - idx_lo + cj - 1) // cj
            idx_lo, idx_hi = idx_lo + ci * span, min(idx_hi, idx_lo + (ci + 1) * span)
        mode = 'seq'

    # 切片: 每片多带一条前驱 (不计数), 覆盖切片边界的值序
    n = idx_hi - idx_lo
    w = max(1, min(a.workers, n))
    per = max(n // w, 1)
    jobs = []
    for k in range(w):
        lo2 = idx_lo + k * per
        hi2 = idx_hi if k == w - 1 else lo2 + per
        if lo2 >= hi2:
            break
        jobs.append((max(idx_lo, lo2 - 1), hi2, a.styles))
    print(f'tier={a.tier} {mode} 起始={idx_lo} 条数={n} workers={len(jobs)}', flush=True)
    with Pool(len(jobs), initializer=_init, initargs=(_VALS,)) as p:
        n_ok = 0
        for r in p.imap_unordered(_worker, jobs):
            if not r['ok']:
                print(f"✗ 错序: {r['kind']} 情形={r['case']} 值={r['value']}", flush=True)
                print(f"  八种写法: {r['forms']}", flush=True)
                if a.report:
                    os.makedirs(os.path.dirname(a.report) or '.', exist_ok=True)
                    with open(a.report, 'w', encoding='utf-8') as f:
                        json.dump(r, f, ensure_ascii=False, indent=2)
                sys.exit(1)
            n_ok += r['n_checked']
            print(f"  ✓ {r['n_checked']} 条  {r['secs']:.1f}s  {r['rate']:.0f} 条/秒", flush=True)
    print(f'全部通过 ({n_ok} 条)', flush=True)


if __name__ == '__main__':
    main()
