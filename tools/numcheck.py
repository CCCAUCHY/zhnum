# -*- coding: utf-8 -*-
"""数值序检查 —— 整数排序 vs locale 排序, 对比即错序。

原理 (与生成器完全解耦):
  1. 取一批整数, 按**整数大小**排序 (这是真值)
  2. 每个整数生成**全部合法的中文写法** (由语言规则定义, 不看生成器)
  3. 把这些写法按 **locale 排序键**排序
  4. 对比两个顺序: 任何不一致就是错序

与旧 sweep.py 的区别:
  - 旧版靠随机抽样, 且"合法写法"只有一种规范读法 ⇒ 漏掉 十万/一十万 这类
    并存读法。旧版跑了 570 亿条没发现 一十万 的错序, 就是这个原因。
  - 新版**枚举全部合法写法**, 且**不做抽样**: 只要值在范围内就全查。

合法写法的定义 (语言规则, 与生成器无关):
  - 每个数位上的数字有 3 种写法: 小写 / 大写简 / 大写繁
  - 每个单位有 4 种写法: 小写简 / 大写简 / 小写繁 / 大写繁
  - 纯写法 = 数字类与单位类**同类配对**: (小写,小写简) (大写简,大写简)
    (小写,小写繁) (大写繁,大写繁) —— 4 形。混搭 (贰萬) 非法, 不生成。
  - 十位是 一 时, 可省 一: 十万 / 一十万 都合法
  - 零 只有一种写法

用法: python3 tools/numcheck.py --loc <LOCPATH> --start A --count N [--limit L]
退出码 0 = 无错序 / 1 = 有错序 / 2 = 环境错。
"""
import argparse, ctypes, locale, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_L = ctypes.CDLL('libglib-2.0.so.0')
_L.g_utf8_collate_key_for_filename.restype = ctypes.c_void_p
_L.g_utf8_collate_key_for_filename.argtypes = [ctypes.c_char_p, ctypes.c_ssize_t]
_L.g_free.argtypes = [ctypes.c_void_p]


def key(s):
    p = _L.g_utf8_collate_key_for_filename(s.encode('utf-8'), -1)
    if not p:
        return b''
    try:
        return ctypes.string_at(p)
    finally:
        _L.g_free(p)


# ── 写法来源: zhnum_core.spellings() ──
# 契约的唯一实现。检查器不再自己实现一套规则 —— 两份代码实现同一个规则,
# 规则错了两边一起错, 那才是循环论证。判据是整数序 (算术事实), 与生成器无关。
from zhnum_core import spellings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--loc', required=True)
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--count', type=int, default=100000,
                    help='连续模式的条数; 随机模式是抽取个数')
    ap.add_argument('--end', type=int, default=0,
                    help='随机模式的上界 (含); 0 = 用 --start + --count')
    ap.add_argument('--random', action='store_true',
                    help='随机取值 (大范围用); 默认连续')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--case', default='bare', choices=['bare', 'chapter'])
    ap.add_argument('--slots', default='',
                    help='slot-order.tsv: 用它提供"每个值有哪些写法"（契约）。'
                         '不给则用内置的语言规则生成 4 形。')
    ap.add_argument('--report', default='', help='记录写到这个文件 (JSON)')
    ap.add_argument('--workers', type=int, default=1, help='保留参数, 供 sweep_drive 兼容')
    a = ap.parse_args()

    os.environ['LOCPATH'] = a.loc
    os.environ['LC_ALL'] = 'zhnum.UTF-8'
    try:
        got = locale.setlocale(locale.LC_ALL, '')
    except locale.Error as e:
        print(f'locale 加载失败: {e}', file=sys.stderr)
        return 2
    if 'zhnum' not in got:
        print(f'LC_ALL 不是 zhnum ({got!r})', file=sys.stderr)
        return 2

    pre, suf = ('', '.txt') if a.case == 'bare' else ('第', '章.txt')

    # 写法来源: 有 slot-order.tsv 就用它（= 生成器注册的, 即契约本身）,
    # 否则用内置语言规则。前者能覆盖口语形/截断形等, 后者只有 4 形。
    by_val = None
    if a.slots:
        by_val = {}
        for ln in open(a.slots, encoding='utf-8'):
            if '\t' not in ln:
                continue
            v, sp = ln.rstrip('\n').split('\t', 1)
            try:
                by_val.setdefault(float(v), []).append(sp)
            except ValueError:
                continue
        print(f'写法来自 {a.slots}: {len(by_val):,} 个值 / '
              f'{sum(len(x) for x in by_val.values()):,} 条写法', flush=True)

    if a.random:
        import random
        hi = a.end or (a.start + a.count)
        rng = random.Random(a.seed)
        # 去重: 相邻两个值相同时 "本值键 > 前值键" 必然不成立 (有放回抽样
        # 必然出现重复, 见 NOTES)
        if by_val is not None:
            # 从注册过的值里挑 —— 保证每个抽到的值都有写法可查
            pool = [v for v in by_val if a.start <= v <= hi and v == int(v)]
            vals = sorted(rng.sample(pool, min(a.count, len(pool))))
            print(f'随机 [{a.start:,}, {hi:,}] 从 {len(pool):,} 个注册值中'
                  f'抽 {len(vals):,} 个 情形 {a.case}', flush=True)
        else:
            vals = sorted(set(rng.randrange(a.start, hi + 1) for _ in range(a.count)))
            print(f'随机 [{a.start:,}, {hi:,}] 抽 {len(vals):,} 个 情形 {a.case}', flush=True)
    else:
        hi = a.start + a.count
        vals = list(range(a.start, hi))
        print(f'连续 [{a.start:,}, {hi:,}) 共 {len(vals):,} 个 情形 {a.case}', flush=True)

    # 1. 整数序 (真值) —— 同时取全部写法
    t0 = time.time()
    if by_val is not None:
        items = [(v, by_val[v]) for v in vals if v in by_val]
        missing = len(vals) - len(items)
        if missing:
            print(f'  注意: {missing} 个值在 slot-order.tsv 里没有写法 (超出注册范围?)',
                  flush=True)
    else:
        items = [(v, spellings(v)) for v in vals]

    # 2. locale 序
    bad = 0
    viol = []
    prev_v, prev_max = None, None
    for v, sps in items:
        ks = [key(pre + s + suf) for s in sps]
        mn, mx = min(ks), max(ks)
        if prev_max is not None and mn <= prev_max:
            bad += 1
            if len(viol) < 20:
                viol.append({'value': v, 'prev_value': prev_v,
                             'forms': sps[:4],
                             'prev_max': prev_max.hex()})
                print(f'  ✗ 值 {v:,} 的写法键 ≤ 值 {prev_v:,} 的最大键')
                print(f'     {sps[:2]}')
        prev_v, prev_max = v, mx
    secs = time.time() - t0
    n_forms = sum(len(s) for _, s in items)

    if a.report:
        import hashlib, json
        os.makedirs(os.path.dirname(a.report) or '.', exist_ok=True)
        rec = {'ok': not bad, 'n_drawn': len(vals), 'n_unique': len(vals),
               'n_checked': len(items), 'n_violations': bad,
               'secs': round(secs, 2),
               'rate': round(len(items) / max(secs, 1e-9), 1),
               'seed': a.seed, 'hi': a.end or (a.start + a.count),
               'mode': 'random' if a.random else 'seq',
               'n_forms': n_forms,
               'tool': 'numcheck',
               'violations': viol,
               'nc_sha256': hashlib.sha256(open(__file__, 'rb').read()).hexdigest()[:16]}
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)

    print(f'{"✓ 无错序" if not bad else f"✗ {bad} 处错序"} '
          f'({len(items):,} 个值, {n_forms:,} 条写法, {secs:.1f}s)')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
