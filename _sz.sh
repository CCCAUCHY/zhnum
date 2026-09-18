#!/bin/bash
cd /home/vmuser/VMshare/zhnum-g
printf '  %-6s %-7s %10s %10s\n' 档 版本 原文 gzip
for t in 亿 万亿 亿亿; do
  for v in pure mixed; do
    a=$(stat -c%s out/$t-$v/zhnum)
    b=$(gzip -c out/$t-$v/zhnum | wc -c)
    printf '  %-6s %-7s %7.1f MB %7.1f MB%s\n' "$t" "$v" \
      $(echo "$a" | awk '{print $1/1048576}') $(echo "$b" | awk '{print $1/1048576}') \
      "$([ "$a" -gt 104857600 ] && echo '   ✗ 超 100MB' || echo '')"
  done
done
