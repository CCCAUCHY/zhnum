# -*- coding: utf-8 -*-
"""tiers_diff.py — 刚生成到 out/ 的产物与仓库 tiers/ 里的比一比, 是否真的变了。

周构建的 `编译 + verify` 那步要 18 分钟(六份 locale 各编一次 + 各 verify
一次)。但它只在**产物真的会变**时才有意义 —— Unihan 没更新、生成器也没改的
周里, 重新编出来的东西和仓库里的逐字节相同, 18 分钟纯属白跑(实测过一次:
七份产物 sha256 全同)。

比较用未压缩内容而不是 .tar.gz 本身: 压缩流随压缩器版本变(与归档格式无关),
拿压缩后的字节比会把"换了 gzip 版本"误判成"产物变了"。

退出码: 0 = 与仓库相同(不用编) / 1 = 有差异(要编) / 2 = 用法或环境错。
用法: python3 tools/tiers_diff.py          # 在仓库根目录跑, 需先跑过生成步骤
"""
import hashlib, os, subprocess, sys

TIERS = {'亿': 10**8, '万亿': 10**12, '亿亿': 10**16}


def member(tar, name):
    """取归档里某个成员的内容; 不存在返回 None"""
    p = subprocess.run(['tar', '-xzOf', tar, name], capture_output=True)
    return None if p.returncode else p.stdout


def main():
    if not os.path.isdir('out') or not os.path.isdir('tiers'):
        print('要在仓库根目录跑 (需要 out/ 与 tiers/)', file=sys.stderr)
        return 2
    diff, same = [], 0
    for t in TIERS:
        for v in ('pure', 'mixed'):
            src, tar = f'out/{t}-{v}/zhnum', f'tiers/{t}-{v}.tar.gz'
            new = open(src, 'rb').read()
            old = member(tar, 'zhnum')
            if old is None:
                diff.append(f'{t}-{v}: 归档里没有 zhnum')
            elif hashlib.sha256(new).digest() != hashlib.sha256(old).digest():
                diff.append(f'{t}-{v}: zhnum 有差异')
            else:
                same += 1
    nb = open('out/亿-pure/zhbase', 'rb').read()
    ob = open('tiers/zhbase', 'rb').read()
    if hashlib.sha256(nb).digest() != hashlib.sha256(ob).digest():
        diff.append('zhbase: 有差异')
    else:
        same += 1
    if diff:
        print('产物有变化, 需要编译+verify: ' + '; '.join(diff))
        return 1
    print(f'产物与仓库逐字节相同 ({same} 份), 跳过编译+verify')
    return 0


if __name__ == '__main__':
    sys.exit(main())
