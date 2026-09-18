#!/bin/bash
# 构建六份产物: 三档 × 两版本 (pure 不含混搭 / mixed 含混搭)。
# 版本语义见 gen_zhnum.py 闭包段: pure = 全小写+全大写两套写法; mixed 再加
# 「小写数字+大写单位」「大写数字+小写单位」两套 (元素数约 2.5 倍)。
# 注意: localedef 必须用 -f charmaps/UTF-8 (补齐版), 否则兼容汉字区段里
# glibc 未收录的 40 个码点会被静默丢弃并排到整个排序最前面.
set -e
cd "$(dirname "$0")"
CHARMAP="$PWD/charmaps/UTF-8"
python3 gen-charmap.py charmaps
for pair in "100000000 亿" "1000000000000 万亿" "10000000000000000 亿亿"; do
  set -- $pair
  for v in pure mixed; do
    echo "=== $1 → $2 / $v ==="
    mkdir -p "out/$2-$v/loc"
    python3 gen_zhnum.py "$1" "out/$2-$v" "$v"
    (cd "out/$2-$v" \
     && LC_ALL=C localedef -f "$CHARMAP" -i "$PWD/zhbase" ./loc/zhbase.UTF-8 \
     && LC_ALL=C localedef -f "$CHARMAP" -i "$PWD/zhnum"  ./loc/zhnum.UTF-8)
  done
done
echo "六份全部编译完成"

./pack_tiers.sh
