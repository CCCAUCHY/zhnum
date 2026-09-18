#!/bin/bash
# 同步产物到 tiers/<档>/<版本>/, 超 GitHub 100MB 单文件上限的压成 zhnum.zip
# (zip 用 Python 的 zipfile。zhbase 三档两版本内容相同, 各目录自含一份便于
# 直接 localedef。)
set -e
cd "$(dirname "$0")"
LIMIT=104857600
for t in 亿 万亿 亿亿; do
  for v in pure mixed; do
    d="tiers/$t/$v"; mkdir -p "$d"
    cp "out/$t-$v/zhbase" "$d/zhbase"
    rm -f "$d/zhnum" "$d/zhnum.zip"
    if [ "$(stat -c%s "out/$t-$v/zhnum")" -gt "$LIMIT" ]; then
      (cd "out/$t-$v" && python3 -c "
import sys, zipfile
# 固定时间戳: zip 默认写入文件 mtime, 会让内容未变的产物每次构建都变字节,
# 周构建因此产生无意义的'有更新'提交。内容 + 固定元数据 = 可复现字节。
zi = zipfile.ZipInfo('zhnum', date_time=(1980, 1, 1, 0, 0, 0))
zi.compress_type = zipfile.ZIP_DEFLATED
zi.external_attr = 0o644 << 16
with zipfile.ZipFile(sys.argv[1], 'w', compresslevel=9) as z:
    z.writestr(zi, open('zhnum', 'rb').read())
" "$OLDPWD/$d/zhnum.zip")
      echo "  $t/$v: zhnum.zip $(du -h "$d/zhnum.zip" | cut -f1)"
    else
      cp "out/$t-$v/zhnum" "$d/zhnum"
      echo "  $t/$v: zhnum $(du -h "$d/zhnum" | cut -f1)"
    fi
  done
done
