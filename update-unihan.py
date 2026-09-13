#!/usr/bin/env python3
"""update-unihan.py — 从 Unicode 官方 Unihan.zip 拉最新数据, 重建三张 tsv.

数据源 (https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip):
  unihan-strokes.tsv  ← kTotalStrokes (取第一个值; 只留基本区 4E00-9FFF)
  unihan-radicals.tsv ← kRSUnicode    (主部首号.残余笔画; 只留 BMP)
  unihan-cangjie.tsv  ← kCangjie      (只留 BMP)

用法: python3 update-unihan.py [输出目录]   (默认: 脚本所在目录)
退出码 0 = 有更新已写盘; 2 = 无变化 (内容逐字节相同, 不动文件).
"""
import io
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else HERE
URL = 'https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip'

def parse():
    """返回 {字段: {码点: 值}}; kRSUnicode 取主部首 (首个条目).
    字段所在文件 (UCD 15+): kTotalStrokes/kRSUnicode 在 IRGSources,
    kCangjie 在 DictionaryLikeData."""
    data = {'kTotalStrokes': {}, 'kRSUnicode': {}, 'kCangjie': {}}
    with urllib.request.urlopen(URL, timeout=120) as r:
        raw = io.BytesIO(r.read())
    with zipfile.ZipFile(raw) as z:
        for member, fields in (('Unihan_IRGSources.txt', ('kTotalStrokes', 'kRSUnicode')),
                               ('Unihan_DictionaryLikeData.txt', ('kCangjie',))):
            with z.open(member) as f:
                for line in io.TextIOWrapper(f, 'utf-8'):
                    if line.startswith('#') or not line.strip():
                        continue
                    cp, field, val = line.split('\t', 2)
                    n = int(cp[2:], 16)
                    if field == 'kCangjie':
                        if n > 0xFFFF:               # 仓颉: 全 BMP (含 A 区)
                            continue
                    elif not (0x4E00 <= n <= 0x9FFF):  # 笔画/部首: 只基本区
                        continue
                    val = val.strip()
                    if field == 'kTotalStrokes':
                        data['kTotalStrokes'].setdefault(n, val)
                    elif field == 'kCangjie':
                        data['kCangjie'].setdefault(n, val)
                    elif field == 'kRSUnicode':
                        # 主部首条目: 形如 "85.4"; 单撇号 (如 196'.5) =
                        # 部首不在该部首常规位置, 剥掉; 双撇号 (如 208''.0)
                        # = 简繁代理字, 跳过.
                        first = val.split()[0]
                        if "''" in first:
                            continue
                        first = first.replace("'", "")
                        rad, rest = first.split('.')
                        data['kRSUnicode'].setdefault(n, f"{rad}\t{rest}")
    return data

def emit(field, table, fmt):
    lines = []
    for n in sorted(table):
        lines.append(f"U+{n:04X}\t{fmt(table[n])}")
    return '\n'.join(lines) + '\n'

FILES = {
    'unihan-strokes.tsv': ('kTotalStrokes', lambda v: v),
    'unihan-radicals.tsv': ('kRSUnicode', lambda v: v),
    'unihan-cangjie.tsv': ('kCangjie', lambda v: v),
}

def main():
    data = parse()
    changed = False
    for fname, (field, fmt) in FILES.items():
        new = emit(field, data[field], fmt)
        path = os.path.join(OUT, fname)
        old = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
        if new != old:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new)
            print(f'{fname}: 更新 ({len(data[field])} 条)')
            changed = True
        else:
            print(f'{fname}: 无变化')
    sys.exit(0 if changed else 2)

if __name__ == '__main__':
    main()
