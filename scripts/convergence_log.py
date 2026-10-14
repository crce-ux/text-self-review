# -*- coding: utf-8 -*-
"""convergence_log.py —— 自查轮次记录 → 能不能判收敛

【为什么有它】
    text-self-review 的收敛判据（C1a / C1b / C2 / C3）是这套流程里唯一
    **完全可判定**的部分：四个数，四条阈值，没有语义空间。
    但人做的时候，最常见的错不是算错，是**忘了 C3**——
    某一轮出现「上轮漏看」，本该**作废**，却被当成「又跑了一轮」，
    于是拿一个掺了水的序列去判收敛。

【输入格式】一个 markdown 表，按**表头名**认列：

    | 轮次 | 维度 | 实质 | 语言 | 未查 | 回流 |
    |---|---|---|---|---|---|
    | R1 | D1,D10 | 3 | 7 | 12 | 0 |
    | R2 | D2,D6  | 1 | 5 |  9 | 1 |

    实质 = C1a 实质类修正数（事实/归因/逻辑/完整性/边界）
    语言 = C1b 语言类修正数（表达/流畅/体例）
    未查 = C2 维度库里还没查过的项数
    回流 = C3 触发数（修正引入的新错 + 上轮漏看），>0 即本轮作废

【判什么】
    C1a 实质 = 0 ｜ C1b 语言 ≤ 2 ｜ C2 未查 ≤ 2 ｜ C3 回流 = 0
    四条**同时成立**才算收敛。任一轮 回流>0 → 该轮作废，不计入序列。
    跑满 6 轮仍未收敛 → 止损：文本结构有问题，重写该部分，而不是继续逐句修。

用法：
    python convergence_log.py <自查记录.md>

退出码：已收敛 0 ｜ 未收敛 1 ｜ 记录格式有问题 2
"""
import argparse
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COLS = ["轮次", "实质", "语言", "未查", "回流"]
MAX_ROUNDS = 6          # convergence.md 的止损线
NUM = re.compile(r"-?\d+")


def table_rows(text):
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows


def parse(text):
    """返回 (表头下标, [ {轮次,实质,语言,未查,回流} ])。找不着表就抛 SystemExit(2)。"""
    rows = table_rows(text)
    idx = None
    for i, cells in enumerate(rows):
        if all(c in cells for c in COLS):
            idx = i
            break
    if idx is None:
        raise SystemExit(
            "记录里没有找到表头 " + " / ".join(COLS) + "。\n"
            "请在自查记录里加一张这样的表：\n"
            "| 轮次 | 维度 | 实质 | 语言 | 未查 | 回流 |\n"
            "|---|---|---|---|---|---|")

    head = rows[idx]
    col = {name: head.index(name) for name in COLS}
    out = []
    for cells in rows[idx + 1:]:
        if len(cells) <= max(col.values()):
            continue
        rec = {"轮次": cells[col["轮次"]]}
        bad = False
        for name in COLS[1:]:
            m = NUM.search(cells[col[name]])
            if m is None:
                bad = True
                break
            rec[name] = int(m.group())
        if bad:
            continue
        out.append(rec)
    if not out:
        raise SystemExit("找到表头了，但一行有效数据都没有。")
    return out


def verdict(rec):
    """单轮判定。返回 (是否通过四条, 触发的原因列表)。"""
    reasons = []
    if rec["实质"] != 0:
        reasons.append(f"C1a 实质 = {rec['实质']}，必须为 0")
    if rec["语言"] > 2:
        reasons.append(f"C1b 语言 = {rec['语言']}，须 ≤ 2")
    if rec["未查"] > 2:
        reasons.append(f"C2 未查 = {rec['未查']}，须 ≤ 2")
    if rec["回流"] > 0:
        reasons.append(f"C3 回流 = {rec['回流']}，**本轮作废**，不计入收敛序列")
    return (not reasons), reasons


def main():
    ap = argparse.ArgumentParser(description="自查轮次记录 → 收敛判定")
    ap.add_argument("log")
    a = ap.parse_args()

    p = pathlib.Path(a.log)
    recs = parse(p.read_text(encoding="utf-8", errors="replace"))

    print(f"convergence_log · {p.name} · {len(recs)} 轮")
    print(f"  {'轮次':<6}{'实质':>5}{'语言':>5}{'未查':>5}{'回流':>5}   判定")
    valid = []
    for r in recs:
        ok, reasons = verdict(r)
        voided = r["回流"] > 0
        tag = "✅ 通过" if ok else ("⛔ 作废" if voided else "❌ 未过")
        print(f"  {r['轮次']:<6}{r['实质']:>5}{r['语言']:>5}{r['未查']:>5}"
              f"{r['回流']:>5}   {tag}")
        if not voided:
            valid.append(r)
        for why in reasons:
            if not why.startswith("C3"):
                print(f"         · {why}")

    voided_n = len(recs) - len(valid)
    if voided_n:
        print(f"\n  ⚠️ {voided_n} 轮因 C3 作废——**作废的轮次不算「又跑了一轮」**。"
              f"\n     它说明该维度的检查深度不够，不是已经查干净了。")

    if not valid:
        print("\n  ❌ 没有一轮成立——先按 C3 把回流清掉再谈收敛。")
        return 1

    last = valid[-1]
    ok, _ = verdict(last)
    if ok:
        print(f"\n  ✅ 收敛：末轮 {last['轮次']} 四条同时成立。")
        return 0

    rounds_used = len(valid)
    if rounds_used >= MAX_ROUNDS:
        print(f"\n  🛑 已跑 {rounds_used} 轮仍未收敛 → **止损**。"
              f"\n     说明文本结构本身有问题（如一句话承载三个断言）——"
              f"\n     **重写该部分，不要继续逐句修。**")
        return 1

    print(f"\n  ❌ 未收敛（有效轮次 {rounds_used}，止损线 {MAX_ROUNDS}）。"
          f"\n     → 换一个**从未用过**的维度重跑，而不是重复通读。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
