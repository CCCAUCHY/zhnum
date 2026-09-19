# 开发与维护笔记

README 讲这个 locale 是什么、怎么用；这里讲**改它的时候要知道什么**。

## 代码结构

| 文件 | 职责 |
|------|------|
| `zhnum_core.py` | 纯逻辑：数字读法 `read()` 与别名闭包 `alias_closure()`。不读文件、不写盘、不看 argv |
| `gen_zhnum.py` | 读数 → 建槽 → 发射 locale 源。`TIER OUTDIR [pure\|mixed]` |
| `gen-charmap.py` | 从系统 charmap 生成补齐版（原因见下） |
| `update-unihan.py` | 从 Unihan.zip 重建三张 tsv；按内容比对判「有更新」 |
| `verify.py` | 排序语义验收，也是周构建的通过门槛 |
| `build_tiers.sh` / `pack_tiers.sh` | 六份产物的一键构建与打包 |
| `tools/` | 其余检查：`alias_spec.py` 别名完备性、`zb_check.py` 默认排序、`perf_nau.py` 性能、`lint_locale.py` 静态检查、`check_all.sh` 汇总 |

## 三条不能违反的不变量

1. **权重列方向**。glibc 的权重分配序是
   `基表符号 < 本地 reorder 新符号 < copy 链块符号`。
   汉字行必须借用基表已有符号（权重4 用 `<U0021>`、权重2 用 `<BASE>`），
   用自己的 token 会被数值槽符号压过，位置分区的列方向翻转。
2. **权重3 恒 IGNORE**。这层带任何值，都会在数值裁决之前插入一层与基表不对称
   的比较，打断位置分区。空着就是它的功能。
3. **别名闭包是唯一入口**。新增注册点一律调 `alias_closure()`，不要手写写法
   列表——漏掉任何一种写法，该串会退化成多原子，而多原子的比较在首原子就终止，
   首原子携带的写法序会压过后缀的数值。

## 容易踩的坑

- `localedef -i <名>` 在 cwd 无对应源文件时**静默回落** `/usr/share` 的装机版；
  实验编译必须给绝对路径。
- 码点不在 glibc 的 UTF-8 charmap 里时，localedef 会**静默丢弃**该行（无告警）。
  兼容汉字区段有 40 个这样的码点（U+FA6E/FA6F/U+FADA..U+FAFF），靠
  `gen-charmap.py` 补齐。动过字符相关逻辑后要复查生成行是否真的落地。
- 别名闭包内部是 set 派生结构，消费前必须 `sorted()`，否则同值槽的注册序会随
  `PYTHONHASHSEED` 抖动，两次构建产出不同文件。
- `pack_tiers.sh` 会把 `out/` 的产物打包提交。数据表比 `out/` 新时它报错退出，
  这是有意的，不要绕过——绕过就会提交一份用旧数据编的产物。
- 压缩流随压缩器版本变（与归档格式无关，zip/gz/tar.gz 都一样），换构建环境后
  第一次运行会产生一次提交，之后稳定。
- `localedef` 的耗时随元素量**超线性**增长：十几万元素是秒级，五十万元素在本机
  （3.8 GB 内存）超过十分钟、峰值 745 MB。编译慢由元素量决定，不是文件坏了。

## 改完必做

```bash
python3 gen_zhnum.py 100000000 out/x mixed    # 单份生成
./build_tiers.sh                              # 六份重建 + 编译 + 打包
./tools/check_all.sh                          # 排序语义 + 别名完备性 + 性能
python3 tools/lint_locale.py out/ tiers/      # 静态检查
```

改动 `gen_zhnum.py` 之后，**先用同一份数据比对重构前后的产物是否逐字节相同**，
再谈别的——这是判断改动是否只动了想动的东西的最快办法。
