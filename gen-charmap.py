# -*- coding: utf-8 -*-
"""从系统 UTF-8 charmap 生成补齐版 charmap (构建用, 产物不入库)。

为什么需要: glibc 的 UTF-8 charmap 只在 F900..FA6D 与 FA70..FAD9 两段区间收
录兼容汉字, FA6E/FA6F 落在两段之间的缺口, FADA..FAFF (Unicode 14 新增) 整段
未收录; 2F800 段的部分码点同理. 码点不在 charmap 里 ⇒ localedef 读 locale
源时无法解析 `<UXXXX>` 记号, 该行被**静默丢弃** (无 warning), 于是这些兼容汉
字拿不到权重, glibc 回落到"一~三级 IGNORE", 排到整个排序最前面 (连拉丁都在
其后), 违反 zhbase "兼容汉字紧跟汉字块"的契约.

做法: 读系统 charmap, 把兼容汉字区段里**缺的码点**按 UTF-8 字节补进去, 输出
到 charmaps/UTF-8. 区段枚举 (而非查表) ⇒ 对 Unicode/glibc 更新天然免疫: 新字
只会落在区内, 系统 charmap 补上后本脚本自然不再重复添加.
用法: python3 gen-charmap.py [输出目录]   (默认 ./charmaps)
"""
import sys, os, gzip, io

SRC = '/usr/share/i18n/charmaps/UTF-8.gz'
# 兼容汉字区段 (Unicode 固定区段). 2F800 段只到 2FA1D — 2FA1E/2FA1F 未分配.
BLOCKS = [(0xF900, 0xFAFF), (0x2F800, 0x2FA1D)]

def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else 'charmaps'
    os.makedirs(outdir, exist_ok=True)
    with gzip.open(SRC, 'rt', encoding='utf-8') as f:
        src = f.read()
    have = set()
    for ln in src.splitlines():
        if ln.startswith('<U') and '>' in ln:
            tok = ln[2:ln.index('>')]
            if '..' not in tok:
                have.add(int(tok, 16))
    add = []
    for lo, hi in BLOCKS:
        for v in range(lo, hi + 1):
            if v in have:
                continue
            esc = ''.join(f'/x{c:02x}' for c in chr(v).encode('utf-8'))
            add.append(f'<U{v:04X}>     {esc} CJK COMPATIBILITY IDEOGRAPH-{v:04X}')
    if not add:
        print(f'系统 charmap 已完整收录兼容汉字区段 ({SRC}), 无需补齐')
    i = src.rindex('END CHARMAP')
    dst = os.path.join(outdir, 'UTF-8')
    io.open(dst, 'w', encoding='utf-8').write(
        src[:i] + '\n'.join(add) + ('\n' if add else '') + src[i:])
    print(f'{dst}: 补齐 {len(add)} 个兼容汉字码点'
          + (f' (U+{add[0].split(">")[0][2:]} …)' if add else ''))

if __name__ == '__main__':
    main()
