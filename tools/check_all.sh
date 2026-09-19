#!/bin/bash
# 六份产物整体验收: 排序语义 (verify.py) + 别名完备性 (alias_spec.py, 按版本
# 口径) + Nautilus 路径性能 (perf_nau.py) + 默认排序 (zb_check.py)。
# 用法: 先 build_tiers.sh 生成 out/, 再跑本脚本。
set -e
cd "$(dirname "$0")/.."          # 仓库根
for t in 亿 万亿 亿亿; do
  for v in pure mixed; do
    echo "########## $t / $v ##########"
    LC_ALL=zhnum.UTF-8 LOCPATH="$PWD/out/$t-$v/loc" python3 verify.py 2>&1 | tail -1
    (cd "out/$t-$v" && STYLES=$v LC_ALL=zhnum.UTF-8 LOCPATH=$PWD/loc \
      python3 ../../tools/alias_spec.py 2>&1 | grep -E '裸数|万级|亿级|合计')
    (cd "out/$t-$v" && LC_ALL=zhnum.UTF-8 LOCPATH=$PWD/loc \
      python3 ../../tools/perf_nau.py 2>&1 | tail -2)
  done
done
echo "########## 默认排序 (zhbase, 六份同内容) ##########"
(cd out/亿-pure && LC_ALL=zhbase.UTF-8 LOCPATH=$PWD/loc python3 ../../tools/zb_check.py 2>&1 | head -4)
