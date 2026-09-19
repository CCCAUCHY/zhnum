#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint_locale.py — zhbase / zhnum locale 源文件的安全静态检查器 (CI 用, 纯标准库)。

范围声明: 本工具只检查 zhbase / zhnum 这两个 locale 源文件本身的供应链/注入
类安全问题。不检查打包形态 (zip)、不检查安装流程 —— 两者都不在本工具范围内,
由使用者自行处理。也不检查排序语义是否正确 (权重契约、别名完备性等由
verify.py / alias_spec.py / zb_check.py 负责, 且需要真正 localedef 编译,
静态扫描做不到)。

检查这三类, 每条都对应一个具体的攻击面, 不含风格 / 正确性断言:

  编码安全   UTF-8 合法性 — 非法字节序列在不同解析器间 (人看的 diff 工具 vs
             localedef 的 C 解析器) 可能被不同解读。
             C0 控制字符 — NUL 会让 C 字符串截断 (文本查看器与 localedef
             读到的内容可能不同)、ESC 可能是操纵 CI 日志显示的终端转义序列、
             裸 CR 会让按行处理的工具与按字节处理的工具读出不同行。
             双向覆盖 / 不可见格式字符 — Trojan Source 一类攻击, 显示顺序
             与实际字节顺序不一致 (无论出现在注释还是数据里都拒绝)。
  内容来源   copy 目标必须在白名单内 (zh_CN / zhbase / iso14651_t1_common)。
             这是 LC_COLLATE 的默认排序来源, 换成白名单外的名字 = 编译时
             静默改用一个未经本仓库审查的排序 / 字符集定义。
  危险指令   include / translit_include — 编译时把本仓库之外的文件内容原文
             拼进来, 是 glibc locale 源语法里最接近"任意文件读取"的东西。

用法:
    python3 tools/lint_locale.py tiers/          # 递归扫目录, 只找 zhbase/zhnum
    python3 tools/lint_locale.py out/亿-pure/zhnum

退出码: 0 = 通过; 1 = 发现问题; 2 = 用法错误。
在 GitHub Actions 下自动输出 ::error 行内注解并写 job summary。
"""
import argparse
import hashlib
import os
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------- 策略配置

# LC_COLLATE 的 copy 目标白名单 (三份产物实测跨六档一致: iso14651_t1_common /
# zh_CN / zhbase, 见 gen_zhnum.py 的 build() )。白名单外的目标一律拒绝。
ALLOWED_COPY = {'zh_CN', 'zhbase', 'iso14651_t1_common'}

# 双向控制与不可见格式字符: 能让肉眼所见与实际字节顺序不一致 (CVE-2021-42574
# "Trojan Source" 一类)。注释行也不放过 —— 注释正是人会去读、不会去逐字节
# 核对的地方。
BIDI_CHARS = (
    '\u061c'                                          # ALM
    '\u200b\u200c\u200d\u200e\u200f'                  # ZWSP/ZWNJ/ZWJ/LRM/RLM
    '\u202a\u202b\u202c\u202d\u202e'                  # LRE/RLE/PDF/LRO/RLO
    '\u2066\u2067\u2068\u2069'                        # LRI/RLI/FSI/PDI
    '\ufeff'                                          # BOM / ZWNBSP
)
_BIDI_BYTES_RE = re.compile(
    b'|'.join(re.escape(c.encode('utf-8')) for c in BIDI_CHARS))
_CTRL_BYTES_RE = re.compile(rb'[\x00-\x09\x0b-\x1f\x7f]')   # \n 除外的 C0 + DEL

_INCLUDE_RE = re.compile(r'^\s*(include|translit_include)\b', re.IGNORECASE)
_COPY_RE = re.compile(r'^\s*copy\s+"([^"]*)"\s*$')

# ---------------------------------------------------------------- 结果收集

class Findings:
    """按 (文件, 代码) 限流, 避免一处系统性问题刷出成千上万条注解。"""

    def __init__(self, cap=10):
        self.cap = cap
        self.items = []
        self.counts = defaultdict(int)
        self.n_err = 0

    def error(self, code, path, line, msg):
        key = (path, code)
        self.counts[key] += 1
        self.n_err += 1
        if self.counts[key] <= self.cap:
            self.items.append((code, path, line, msg))
        elif self.counts[key] == self.cap + 1:
            self.items.append(
                (code, path, line, f'(同类问题过多, 后续 {code} 不再逐条列出)'))


def _esc(s, prop=False):
    s = s.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    return s.replace(':', '%3A').replace(',', '%2C') if prop else s


def emit(F, in_actions):
    for code, path, line, msg in F.items:
        if in_actions:
            loc = f'file={_esc(path, True)}'
            if line:
                loc += f',line={line}'
            print(f'::error {loc},title={code}::{_esc(msg)}')
        else:
            where = f'{path}:{line}' if line else path
            print(f'  [ERROR] {code}  {where}  {msg}')


# ---------------------------------------------------------------- 字节层

def scan_bytes(path, F):
    """流式扫描原始字节: 控制字符 / 双向覆盖字符。返回 sha256 摘要 (信息性,
    不构成断言 —— 供事后核对产物是否与某次已知构建一致用)。"""
    hits = []
    tail = b''
    offset = 0
    sha = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(4 << 20)
            if not chunk:
                break
            sha.update(chunk)
            buf = tail + chunk
            base = offset - len(tail)
            for rx, code in ((_CTRL_BYTES_RE, 'E002'), (_BIDI_BYTES_RE, 'E003')):
                for m in rx.finditer(buf):
                    hits.append((code, base + m.start(), m.group()))
            tail = buf[-4:]          # 防止多字节序列被切断在 chunk 边界
            offset += len(chunk)

    if hits:
        starts = _line_starts(path)
        seen = set()
        for code, off, raw in hits:
            if (code, off) in seen:
                continue
            seen.add((code, off))
            line = _line_of(starts, off)
            if code == 'E002':
                b = raw[0]
                hint = {
                    0x00: ' (NUL — C 字符串在此截断, 文本查看器与 localedef '
                          '的 C 解析器可能读到不同内容)',
                    0x1b: ' (ESC — 可能是 ANSI 终端转义序列, 会操纵 CI 日志'
                          '的显示)',
                    0x0d: ' (CR — 与 LF 混用会让按行处理的工具与按字节处理'
                          '的工具读出不同行)',
                }.get(b, '')
                F.error(code, path, line, f'控制字符 0x{b:02x}{hint}: 字节偏移 {off}')
            else:
                F.error(code, path, line,
                        f'双向覆盖/不可见格式字符 {raw!r} (字节偏移 {off}) — '
                        'Trojan Source 类攻击手法, 显示顺序可能与字节顺序不一致')
    return sha.hexdigest()


def _line_starts(disk_path):
    starts, off = [0], 0
    with open(disk_path, 'rb') as f:
        while True:
            chunk = f.read(4 << 20)
            if not chunk:
                break
            base = off
            i = chunk.find(b'\n')
            while i >= 0:
                starts.append(base + i + 1)
                i = chunk.find(b'\n', i + 1)
            off += len(chunk)
    return starts


def _line_of(starts, off):
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= off:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


# ---------------------------------------------------------------- 文本层

def scan_text(path, F):
    """UTF-8 合法性 + 危险指令 (include) + 来源白名单 (copy)。
    不做任何 locale 语法结构假设 (段落配对、reorder 嵌套等) —— 那是正确性
    检查; 安全检查只关心这两个模式是否出现, 出现在哪个位置都一样拒绝。"""
    try:
        with open(path, encoding='utf-8', errors='strict') as fh:
            for lineno, raw in enumerate(fh, 1):
                line = raw.rstrip('\n')
                if _INCLUDE_RE.match(line):
                    F.error('E010', path, lineno,
                            f'出现 include/translit_include 指令: {line[:80]!r} '
                            '— 编译时会把本仓库之外、未经审查的文件内容原文'
                            '拼接进来, 一律拒绝')
                    continue
                m = _COPY_RE.match(line)
                if m and m.group(1) not in ALLOWED_COPY:
                    F.error('E012', path, lineno,
                            f'copy 目标 "{m.group(1)}" 不在白名单 '
                            f'{sorted(ALLOWED_COPY)} — 会让该 LC 类别静默'
                            '改用未经审查的排序/字符集定义')
    except UnicodeDecodeError as e:
        F.error('E001', path, 0, f'非法 UTF-8 字节序列, 解码失败: {e}')


# ---------------------------------------------------------------- 驱动

def collect(paths):
    """目录: 递归找文件名恰为 zhbase / zhnum 的文件 (zip 封装不在范围内,
    walk 不会捡到 zhnum.zip)。直接给出的文件路径原样接受, 不做文件名过滤 ——
    方便单独测试任意路径。"""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for fn in sorted(files):
                    if fn in ('zhbase', 'zhnum'):
                        out.append(os.path.join(root, fn))
        else:
            out.append(p)
    return sorted(set(out))


def main():
    ap = argparse.ArgumentParser(
        description='zhbase/zhnum locale 产物安全静态检查 (供应链/注入类问题; '
                    '排序语义正确性见 verify.py)')
    ap.add_argument('paths', nargs='+',
                    help='文件或目录 (目录会递归找 zhbase/zhnum)')
    ap.add_argument('--max-report', type=int, default=10,
                    help='同一文件同一代码最多列出几条 (默认 10)')
    args = ap.parse_args()

    in_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    F = Findings(cap=args.max_report)
    targets = collect(args.paths)
    if not targets:
        print('没有找到任何待检文件', file=sys.stderr)
        return 2

    digests = {}
    for path in targets:
        if not os.path.exists(path):
            F.error('E000', path, 0, '文件不存在')
            continue
        if path.endswith('.zip'):
            # zip 封装不在本工具范围内 (见文件头范围声明); 只有直接把 .zip
            # 路径传给命令行才会走到这里 —— 目录扫描已经不会选中它。跳过而
            # 非当文本扫描, 否则压缩后的二进制字节会被误判成"非法 UTF-8"。
            print(f'  [跳过]   zip 封装不在检查范围内: {path}')
            continue

        sha = scan_bytes(path, F)
        scan_text(path, F)
        digests[path] = (sha, os.path.getsize(path))

    print(f'== 检查 {len(targets)} 个产物 ==')
    for label in sorted(digests):
        sha, size = digests[label]
        print(f'  {sha[:16]}…  {size:>12,}  {label}')
    print()
    if F.items:
        emit(F, in_actions)
        print()
    print(f'结果: error {F.n_err}')

    if in_actions and (sm := os.environ.get('GITHUB_STEP_SUMMARY')):
        with open(sm, 'a', encoding='utf-8') as f:
            ok = F.n_err == 0
            f.write(f'\n### locale 产物安全检查 {"✅" if ok else "❌"}\n\n')
            f.write(f'{len(targets)} 个产物 — error {F.n_err}\n\n')
            f.write('| SHA-256 | 字节 | 产物 |\n|---|---:|---|\n')
            for label in sorted(digests):
                sha, size = digests[label]
                f.write(f'| `{sha[:16]}…` | {size:,} | `{label}` |\n')

    return 1 if F.n_err else 0


if __name__ == '__main__':
    sys.exit(main())
