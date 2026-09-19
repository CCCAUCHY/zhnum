#!/bin/bash
# 汇总产物到 tiers/:
#   tiers/zhbase                  —— 六份共用一份 (三档两版本的 zhbase 完全相同,
#                                    脚本里先断言, 不同则报错而不是静默覆盖)
#   tiers/<档>/<版本>/zhnum       —— 或 zhnum.zip (超 GitHub 100MB 单文件上限时)
# zhnum 用 copy "zhbase", 编译时两者须同目录可见 —— 部署时把 zhbase 与所选
# zhnum 放到一起即可 (见 README「产物」段)。
set -e
cd "$(dirname "$0")"
LIMIT=104857600

REF=out/亿-pure/zhbase
for t in 亿 万亿 亿亿; do
  for v in pure mixed; do
    cmp -s "$REF" "out/$t-$v/zhbase" || {
      echo "::error::out/$t-$v/zhbase 与 $REF 不同 —— zhbase 应六份相同" >&2; exit 1; }
  done
done
mkdir -p tiers && cp "$REF" tiers/zhbase

for t in 亿 万亿 亿亿; do
  for v in pure mixed; do
    d="tiers/$t/$v"; mkdir -p "$d"
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
echo "  zhbase: $(du -h tiers/zhbase | cut -f1) (六份共用)"
