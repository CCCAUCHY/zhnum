#!/bin/bash
# 构建三份产物: 三档 × 纯写法 (全小写/全大写, 各带简繁)。
# 混搭写法 (小写数字+大写单位之类) 已整体废弃: 不是实际书写习惯, 实测有跨
# 风格错序, 编译还更慢 (亿-mixed 比 亿亿-pure 还久)。
# charmap 用系统自带的: zhbase 的汉字以 Unihan 为准, 基表附带的兼容汉字
# 不在设计范围内, 不再需要补齐版 charmap。
set -e
cd "$(dirname "$0")"
TMPDIR_ABS="$(cd "${TMPDIR:-/tmp}" && pwd)"
CHARMAP="$TMPDIR_ABS/charmap.$$"
trap 'rm -f "$CHARMAP"' EXIT
zcat /usr/share/i18n/charmaps/UTF-8.gz > "$CHARMAP"
for pair in "100000000 亿" "1000000000000 万亿" "10000000000000000 亿亿"; do
  set -- $pair
  echo "=== $1 → $2 ==="
  mkdir -p "out/$2/loc"
  python3 gen_zhnum.py "$1" "out/$2"
  (cd "out/$2" \
   && LC_ALL=C localedef -f "$CHARMAP" -i "$PWD/zhbase" ./loc/zhbase.UTF-8 \
   && LC_ALL=C localedef -f "$CHARMAP" -i "$PWD/zhnum"  ./loc/zhnum.UTF-8)
done
echo "三份全部编译完成"

./pack_tiers.sh
