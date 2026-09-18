#!/bin/bash
# 六份产物验收: verify (双路径) + 别名完备性 (按版本口径) + Nautilus 性能
cd "$(dirname "$0")"
for t in 亿 万亿 亿亿; do
  for v in pure mixed; do
    echo "########## $t / $v ##########"
    LC_ALL=zhnum.UTF-8 LOCPATH="$PWD/out/$t-$v/loc" python3 verify.py 2>&1 | tail -1
    (cd "out/$t-$v" && STYLES=$v LC_ALL=zhnum.UTF-8 LOCPATH=$PWD/loc \
      python3 ../../alias_spec.py 2>&1 | grep -E '裸数|万级|亿级|合计')
    (cd "out/$t-$v" && LC_ALL=zhnum.UTF-8 LOCPATH=$PWD/loc python3 ../../perf_nau.py 2>&1 | tail -2)
  done
done
