# -*- coding: utf-8 -*-
"""从 slot-order.tsv 直接验证排序 —— 不自己推读法, 不靠随机抽样。

为什么这么设计:
  - 老检查器自己实现一套 整数→中文, 和生成器的读法一旦不一致, 就会去查
    生成器根本没注册的串 (实测: 一十万 的错序就是这样躲过几亿条抽样)。
  - slot-order.tsv 是生成器**实际注册**的全部写法, 每行 `值<TAB>写法`,
    顺序即注册序。拿它当权威来源, 检查器与生成器就不可能各说各话。

检查内容:
  1. 注册序 == 值序: 按注册序扫一遍, 值必须单调不减
  2. 同值组: 两两 GLib 键 ≠ (各占一槽的副产品, 不是契约条款)
  3. 值序: 每个值取全部写法的键, 必须严格大于前一值的全部键

注意第 3 条比契约强: 它要求跨类的全局单调, 而契约只保证同类内序。
检查器把它当参考指标 —— 报出来的跨类错序属于「不同类之间的顺序不保证」,
不是缺陷。但本检查器只遍历 slot-order.tsv 里注册过的写法, 所以这类跨类
问题通常不会在这里现身 (它们是 numcheck 不带 --slots 时的假阳性来源)。

第 2 条对值 0 (零/〇) 和括号序数组 (0.1..0.3) 跳过: 这些组的写法本来就
允许相等或另有分组语义。

用法: python3 tools/slotcheck.py --loc <LOCPATH> --slots <slot-order.tsv>
      [--case bare|chapter]  [--max N]
退出码 0 = 全部通过 / 1 = 发现错序 / 2 = 环境错。
"""
import argparse, ctypes, locale, os, sys

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


CASES = {
    'bare':    ('', '.txt'),
    'chapter': ('第', '章.txt'),
}


def load_slots(path):
    """返回 [(值, 写法)] —— 保持文件顺序 (即注册序)"""
    out = []
    for ln in open(path, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if not ln or '\t' not in ln:
            continue
        v, sp = ln.split('\t', 1)
        try:
            out.append((float(v), sp))
        except ValueError:
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--loc', required=True)
    ap.add_argument('--slots', required=True)
    ap.add_argument('--case', default='bare', choices=list(CASES))
    ap.add_argument('--max', type=int, default=0, help='只查前 N 行 (0 = 全部)')
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

    slots = load_slots(a.slots)
    if a.max:
        slots = slots[:a.max]
    pre, suf = CASES[a.case]
    print(f'注册写法 {len(slots):,} 条, 情形 {a.case}', flush=True)

    bad_order = bad_equal = bad_value = 0
    prev_max = None
    cur_val, cur_keys = None, []
    n_vals = 0

    def flush_group():
        """一个值结束时: 检查同值组内两两不等值。

        例外: 括号序数组 (值 0.1/0.2/0.3) 跳过 —— 全角/半角括号
        （上）/ (上) 经 GLib 归一化后键相同, 这是 GLib 的 NFKC 行为,
        locale 层无法干预 (strxfrm 路径下两者不等值)。README 已记为
        已知例外。值 0 (零/〇) 不跳过: 两者键确实不等。"""
        nonlocal bad_equal
        if cur_val is not None and 0 < cur_val < 1:
            return                      # 括号序数的值域 (0.1/0.2/0.3)
        for i in range(len(cur_keys)):
            for j in range(i + 1, len(cur_keys)):
                if cur_keys[i] == cur_keys[j]:
                    bad_equal += 1
                    return

    for val, sp in slots:
        k = key(pre + sp + suf)
        if val != cur_val:
            if cur_val is not None:
                if val < cur_val:          # 注册序倒退 (值变小)
                    bad_order += 1
                flush_group()
                n_vals += 1
                if prev_max is not None and cur_keys and min(cur_keys) <= prev_max:
                    bad_value += 1
                    if bad_value <= 5:
                        print(f'  ✗ 值 {cur_val} 的写法键 ≤ 前值最大键')
                prev_max = max(cur_keys) if cur_keys else prev_max
            cur_val, cur_keys = val, []
        cur_keys.append(k)
    if cur_val is not None:
        flush_group()
        n_vals += 1

    print(f'值组 {n_vals:,} 个')
    print(f'  注册序倒退: {bad_order}')
    print(f'  同值等值:   {bad_equal}')
    print(f'  值序越界:   {bad_value}')
    ok = not (bad_order or bad_equal or bad_value)
    print('✓ 全部通过' if ok else '✗ 有错序')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
