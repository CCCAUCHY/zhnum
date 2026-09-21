# -*- coding: utf-8 -*-
"""sweep_drive.py — 自适应轮次的抽样驱动: 按剩余时间决定每一轮抽多少条。

工作流发 6 个版本 × N 个 job (sweep-level.txt 第一行 = N, 默认 3 → 18 个 job),
**每个 job 跑一条 lane**: 编译自己那个版本的 locale 一次 (轮次之间复用, 不重编译),
然后在 job 时间里反复抽样:

    跑一轮 → 记这一轮的真实速度 → 看还剩多少时间 → 决定下一轮的条数 → 再跑

条数上限由 --round-max 定 (默认 100 万), 下限 --round-min (默认 1 万, 装不下就
收工)。单轮条数不再是常数 —— 快的版本自动多抽, 慢的自动少抽, 让每个 job 都在
预算内跑满。

也支持一个 job 跑多条 lane (--lanes 给逗号列表, 默认六个版本全跑): 那种情况下
每条 lane 固定 --workers 1, 让 6 条 lane (而不是 6×4=24 个进程) 去喂 4 个 vCPU。
一个 job 只跑一条 lane 时给 --workers 4。

**每轮结束就提交**那一轮的结果 (无错序也提交) —— job 被 6 小时上限砍掉时,
已完成的轮次不会丢。记录里带样本指纹 (种子 + 区间 + sweep.py 哈希 + locale 哈希),
无错序的轮次也能按它精确重建样本数组; 发现错序的那一轮另存字面数组 .sample.gz。

用法:
  python3 tools/sweep_drive.py --budget 18000 --round-max 1000000 --workers 4 \\
      --lanes 亿:mixed --loc-root /tmp/loc --report-dir reports --run-id 123 --commit
"""
import argparse, json, os, random, subprocess, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWEEP = os.path.join(ROOT, 'tools', 'sweep.py')
TIERS = ('亿', '万亿', '亿亿')
VERS = ('pure', 'mixed')
# 首轮用的保守先验 (条/秒): 只在小预算时才起作用 (大预算下首轮直接顶到上限)。
# 实测本机 4 worker: 亿 mixed ~600 / 万亿 ~330 / 亿亿 ~167, 单进程再除以 ~4。
PRIOR = {'pure': 60.0, 'mixed': 30.0}
PRINT_LOCK = threading.Lock()
GIT_LOCK = threading.Lock()


def log(msg):
    with PRINT_LOCK:
        print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def commit_round(files, msg, tries=5):
    """提交这一轮的结果。--mixed 而不是 --soft: 索引要回到 origin/main,
    否则提交出来的树 = 本进程检出时的旧树 + 新文件, 会抹掉别的 run 刚提交的
    东西 (工作区里新写的报告是未跟踪的, --mixed 不影响)。"""
    with GIT_LOCK:
        for i in range(tries):
            subprocess.run(['git', 'fetch', '-q', 'origin', 'main'], cwd=ROOT)
            subprocess.run(['git', 'reset', '-q', '--mixed', 'origin/main'], cwd=ROOT)
            subprocess.run(['git', 'add', '-f'] + files, cwd=ROOT)
            c = subprocess.run(['git', '-c', 'user.name=zhnum-bot',
                                '-c', 'user.email=actions@github.com',
                                'commit', '-q', '-m', msg], cwd=ROOT)
            if c.returncode != 0:
                log('提交: 无新内容, 跳过')
                return False
            if subprocess.run(['git', 'push', '-q', 'origin', 'HEAD:main'],
                              cwd=ROOT).returncode == 0:
                log(f'提交: {msg}')
                return True
            log(f'推送冲突, 第 {i + 1} 次重试')
            time.sleep(random.randint(5, 15))
        log('提交: 5 次都失败, 这一轮留在工作区')
        return False


def run_lane(tier, ver, ctx):
    loc = os.path.join(ctx.loc_root, f'{tier}-{ver}')
    tag = f'{tier}/{ver}'
    rate = PRIOR[ver]                    # 条/秒, 首轮用先验, 之后用实测
    total = n_viol = rounds = 0
    script_err = False
    recs = []                            # 本 lane 各轮的记录, 累积进一个文件
    while True:
        remain = ctx.deadline - time.time()
        n = int(remain / ctx.margin * rate)
        n = max(ctx.round_min, min(ctx.round_max, n))
        est = n / rate
        if est * ctx.margin > remain:
            log(f'{tag} 收工: 剩 {remain / 60:.0f} 分, 装不下最小轮 '
                f'({ctx.round_min} 条 ≈ {ctx.round_min / rate / 60:.0f} 分)')
            break
        seed = ctx.seed_base + rounds * 104729
        # sweep.py 把这一轮的记录写到临时文件; 读进来后累积进**每 lane 每次运行
        # 一个**的汇总文件。不每轮一个文件: 那样 18 个 job 一天几百个文件。
        # 文件名只含 (档, 版本, run-id) —— 唯一, 所以并行 job 不会互相覆盖
        # (它们各自加自己的行也不行: 同一个文件被两边改写会丢内容)。
        tmp = os.path.join(ROOT, '.sweep-tmp', f'{tier}-{ver}-r{rounds}-{ctx.run_id}.json')
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        cmd = [sys.executable, SWEEP, '--tier', tier, '--styles', ver,
               '--sample', str(n), '--seed', str(seed), '--workers', str(ctx.workers),
               '--report', tmp]
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                           env=dict(os.environ, LC_ALL='zhnum.UTF-8', LOCPATH=loc))
        dt = time.time() - t0
        if p.returncode >= 2 or not os.path.exists(tmp):
            script_err = True
            log(f'{tag} ✗ sweep.py 退出码 {p.returncode} (脚本错, 不是错序), '
                f'本 lane 停止\n{p.stderr.strip()[-400:]}')
            break
        rec = json.load(open(tmp, encoding='utf-8'))
        os.remove(tmp)
        rate = max(rec['rate'], 1.0)     # 实测速度, 下一轮按它排
        rounds += 1
        total += rec['n_checked']
        n_viol += rec['n_violations']
        # 瘦身: 绿色轮次只留"能复算这一轮"的要素 (~250 字节), 错序轮次才带上
        # 写法/键 (那才是要分析的)。不瘦的话一年光是绿色记录也有上百 MB。
        slim = {k: rec[k] for k in ('n_drawn', 'n_unique', 'n_checked', 'secs',
                                    'rate', 'ok', 'n_violations', 'seed', 'hi',
                                    'sample_sha256') if k in rec}
        slim['k'] = rounds
        if rec.get('violations'):
            slim['violations'] = rec['violations']
        recs.append(slim)
        mark = '✗' if rec['n_violations'] else '✓'
        log(f'{tag} {mark} 第 {rounds} 轮 {rec["n_checked"]} 条 {dt / 60:.1f} 分 '
            f'{rate:.0f} 条/秒 剩 {remain / 60:.0f} 分 → 下轮 {min(ctx.round_max, int(max(1, (remain - dt) / ctx.margin * rate)))} 条')
        agg = os.path.join(ctx.report_dir, time.strftime('%F', time.gmtime()),
                           f'{tier}-{ver}-{ctx.run_id}.json')
        os.makedirs(os.path.dirname(agg), exist_ok=True)
        with open(agg, 'w', encoding='utf-8') as f:
            json.dump({'tier': tier, 'styles': ver, 'run_id': ctx.run_id,
                       'start': 1, 'swp_sha256': rec.get('swp_sha256'),
                       'loc_sha256': rec.get('loc_sha256'),
                       'sample_expr_tpl': '_r = random.Random(<seed>); sorted(set('
                                          '_r.randrange(<start>, <hi>) for _ in '
                                          'range(<n_drawn>)))',
                       'rounds': recs}, f, ensure_ascii=False, indent=1)
        commit_round([agg], f'抽样 {tag} run {ctx.run_id}: {len(recs)} 轮 / {total} 条, '
                            f'{"错序 %d 例" % n_viol if n_viol else "无错序"}')
    log(f'{tag} 结束: {rounds} 轮 / {total} 条 / 错序 {n_viol} 例'
        + ('  ← 脚本错导致提前停止' if script_err else ''))
    return total, n_viol, script_err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--budget', type=int, required=True, help='本进程的总预算 (秒)')
    ap.add_argument('--round-max', type=int, default=1000000, help='单轮上限')
    ap.add_argument('--round-min', type=int, default=10000, help='单轮下限')
    ap.add_argument('--report-dir', default='reports')
    ap.add_argument('--loc-root', required=True, help='locale 根目录 (每个 lane 一个子目录)')
    ap.add_argument('--run-id', default='0')
    ap.add_argument('--workers', type=int, default=1,
                    help='每条 lane 给 sweep.py 的 worker 数。一个 job 跑一条 lane 时'
                         '给 4 (整个 runner 归它); 一个 job 跑多条 lane 时给 1')
    ap.add_argument('--seed-base', type=int, default=0)
    ap.add_argument('--margin', type=float, default=1.15, help='给下一轮留的余量')
    ap.add_argument('--lanes', default=','.join(f'{t}:{v}' for t in TIERS for v in VERS))
    ap.add_argument('--commit', action='store_true')
    a = ap.parse_args()
    if not a.commit:
        globals()['commit_round'] = lambda *x, **y: False
    ctx = argparse.Namespace(deadline=time.time() + a.budget, round_max=a.round_max,
                             round_min=a.round_min, report_dir=a.report_dir,
                             loc_root=a.loc_root, run_id=a.run_id, margin=a.margin,
                             workers=a.workers, seed_base=a.seed_base or int(time.time()))
    lanes = [tuple(s.split(':')) for s in a.lanes.split(',') if s]
    for tier, ver in lanes:
        if not os.path.isdir(os.path.join(a.loc_root, f'{tier}-{ver}')):
            sys.exit(f'缺少 locale 目录: {os.path.join(a.loc_root, f"{tier}-{ver}")}')
    log(f'预算 {a.budget / 60:.0f} 分, 单轮 {a.round_min}..{a.round_max} 条, '
        f'{len(lanes)} 条 lane, 交提交={a.commit}')
    res = {}
    ths = [threading.Thread(target=lambda t=t, v=v: res.__setitem__((t, v), run_lane(t, v, ctx)),
                            daemon=True) for t, v in lanes]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    tot = sum(r[0] for r in res.values())
    vio = sum(r[1] for r in res.values())
    err = sum(1 for r in res.values() if r[2])
    log(f'全部 lane 结束: 共 {tot} 条, 错序 {vio} 例'
        + (f', {err} 条 lane 因脚本错停止' if err else ''))
    # 退出码: 0 干净 / 1 发现错序 / 2 有 lane 脚本错 —— 后者必须让 job 变红,
    # 否则"编译全挂、0 条"会伪装成成功 (踩过一次)。
    if err:
        return 2
    return 1 if vio else 0


if __name__ == '__main__':
    sys.exit(main())
