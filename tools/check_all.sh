#!/bin/bash
# 三档产物整体验收: 排序语义 (verify.py) + 槽注册序 (slotcheck.py) +
# 别名完备性 (alias_spec.py) + Nautilus 路径性能 (perf_nau.py) +
# 默认排序 (zb_check.py)。
# 用法: 先 build_tiers.sh 生成 out/, 再跑本脚本。
set -e
cd "$(dirname "$0")/.."          # 仓库根
for t in 亿 万亿 亿亿; do
  echo "########## $t ##########"
  LC_ALL=zhnum.UTF-8 LOCPATH="$PWD/out/$t/loc" python3 verify.py 2>&1 | tail -1
  # 槽注册序: 直接读生成器输出的 slot-order.tsv (权威来源, 不自己推读法)
  python3 tools/slotcheck.py --loc "$PWD/out/$t/loc" \
    --slots "$PWD/out/$t/slot-order.tsv" --case bare 2>&1 | tail -4
  python3 tools/slotcheck.py --loc "$PWD/out/$t/loc" \
    --slots "$PWD/out/$t/slot-order.tsv" --case chapter 2>&1 | tail -2
  (cd "out/$t" && LC_ALL=zhnum.UTF-8 LOCPATH=$PWD/loc \
    python3 ../../tools/alias_spec.py 2>&1 | grep -E '裸数|万级|亿级|合计')
  (cd "out/$t" && LC_ALL=zhnum.UTF-8 LOCPATH=$PWD/loc \
    python3 ../../tools/perf_nau.py 2>&1 | tail -2)
done
echo "########## 默认排序 (zhbase, 三份同内容) ##########"
(cd out/亿 && LC_ALL=zhbase.UTF-8 LOCPATH=$PWD/loc python3 ../../tools/zb_check.py 2>&1 | head -4)
