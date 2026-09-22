#!/bin/bash
# 汇总产物到 tiers/:
#   tiers/zhbase                 —— 三份共用一份 (内容由 unihan-*.tsv 决定, 三份
#                                   逐字节相同; 下面会断言, 不同即报错)
#   tiers/<档>.tar.gz            —— 只装该档的 zhnum
# zhbase 不塞进每个包: 那样等于把共用文件复制三遍。zhnum 用 copy "zhbase",
# 编译时两者须同目录可见 —— 解开包再把 tiers/zhbase 放到一起即可。
#
# 为什么用 tar: 确定性元数据用标准 CLI 参数就能表达 (--sort/--mtime/--owner/
# --group/--numeric-owner), 不必手写归档格式; -C <dir> 让源目录位置不进归档。
# 实测同一输入两次构建、以及从不同路径打包, 产物逐字节相同。
# 压缩流本身仍随压缩器版本变 (与归档格式无关), 换构建环境后第一次运行会产生
# 一次提交; 周构建环境固定, 之后稳定。
#
# 数据新鲜度: zhbase 的内容由 unihan-*.tsv 决定, 数据表比产物新说明 out/ 是
# 旧数据编的, 此时打包会把过期内容提交上去 —— 直接拦住。
set -e
cd "$(dirname "$0")"

REF=out/亿/zhbase
for f in unihan-*.tsv; do
  if [ "$f" -nt "$REF" ]; then
    echo "::error::$f 比 $REF 新 —— out/ 是旧数据编的, 请先重建再打包" >&2
    exit 1
  fi
done
for t in 亿 万亿 亿亿; do
  cmp -s "$REF" "out/$t/zhbase" || {
    echo "::error::out/$t/zhbase 与 $REF 不同 —— zhbase 应三份相同" >&2; exit 1; }
done

rm -f tiers/*.tar.gz
mkdir -p tiers
cp "$REF" tiers/zhbase
for t in 亿 万亿 亿亿; do
  d="out/$t"
  tar --sort=name --mtime='@0' --owner=0 --group=0 --numeric-owner \
      -czf "tiers/$t.tar.gz" -C "$d" zhnum
  printf '  %-8s %s\n' "$t" "$(du -h "tiers/$t.tar.gz" | cut -f1)"
done
echo "  zhbase    $(du -h tiers/zhbase | cut -f1)  (三份共用)"
echo "  合计 $(du -sh tiers | cut -f1)"
