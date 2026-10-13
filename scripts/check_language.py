# -*- coding: utf-8 -*-
"""
check_language.py —— 文稿「可理解性 + 引用自足性 + 断言严谨性」自动检查

【用途】
    补 `PPT文稿去味清单.md` 的缺口。去味清单管的是「文字像不像人话」（AI 味、套话），
    本脚本管的是「内容能不能被接住、断言站不站得住」——五类可自动化的检查：
      ① 回指词        —— 引用必须自足，禁用「那篇综述」「该研究」
      ② 排他性断言    —— 唯一/首次/主流/无效/不独特… 必须能指到具体出处
      ③ 空泛量词      —— 很多/一些/大量… 除非后面接具体数字
      ④ 缩写未展开    —— 首次出现的小写全大写串，附近有无中文全称/括号解释
      ⑤ 数字-口径汇总 —— 列出所有百分比/倍数及其上下文，供人工核口径

    检查①③④是启发式，**一律需要人工复核**；② 是硬规则（排他性断言必须有出处）。

【对应流程】
    `文献调研流程手册.md` 质量核查 —— 出稿门禁 G2 的语言层
    配套 `_系统/_流程与工具/内容自检清单.md`

【用法】
    python check_language.py 组会汇报_讲稿.md
    python check_language.py 讲稿.md 参考稿.md 制作稿.md          # 多文档一起查
    python check_language.py 讲稿.md --terms 术语白名单.txt        # 跳过已知术语
    python check_language.py 讲稿.md --only 1,2                    # 只跑第 1、2 类
    python check_language.py 讲稿.md --quiet                       # 只输出汇总
    退出码 = 发现问题总数（可用于 CI/门禁）

【术语白名单文件格式】
    每行一个，`#` 开头为注释。可用 `TERM=中文全称` 形式提供建议展开。
        DOI
        PMID
        TRS=治疗抵抗性精神分裂症

【依赖】标准库

【踩坑教训（2026-09-14 建立）】
    · 「缩写未展开」的启发式会误报通用词（AI/USB/DNA 等），故内置 SKIP 列表；
      专业词请用 `--terms` 白名单，不要改脚本——脚本是全项目共享的。
    · 回指词在**讲稿口播**里有时可接受（承接清晰的顿句），故只报不改，交人工判。
    · 排他性断言的"有出处"判据是：±40 字内出现 [n] 角标 / 四位年份 / "等"后人名。
      参考文献表内的条目本身会被跳过，避免自证。

【冒烟测试】
    2026-09-14 于 `屏状核_氯氮平/04_组会汇报/组会汇报_讲稿_v3_新页序_20260914.md`（约 630 行）
    通过；命中回指数 0、排他性断言 2（"唯一"2 处，均有出处）、缩写待查 11。
"""
import argparse
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── ① 回指词：引用不自足 ────────────────────────────────────────
ANAPHORA = [
    r"那篇(?:综述|文章|论文|研究|文献)",
    r"该(?:研究|文|综述|文章|论文)",
    r"前述(?:文献|研究)?",
    r"上述(?:文献|研究)",
    r"(?:上|前)面(?:提到|说到|讲过)的(?:那|这|该)?(?:篇|个|项)?",
    r"这项研究",
    r"这篇(?:综述|文章|论文)",
]

# ── ② 排他性断言：必须能指到出处 ────────────────────────────────
EXCLUSIVE = [
    r"唯一", r"首次", r"首个", r"第一个", r"独创",
    r"(?:当前)?主流", r"无效", r"不独特", r"没有区分力",
    r"(?:无人|没人|没有人)(?:做过|研究过|问过)",
    r"零篇", r"从未(?:有人|被)", r"无一(?:例|篇)",
    r"没有任何(?:一项|一个|研究)",
    r"(?:均|都)未(?:达标|通过)",
]

# 有出处的判据：±40 字内有 [n] / (n) / 四位年份 / 「等」
CITE_PAT = re.compile(r"\[\d+\]|（\d+）|\(\d+\)|(?:19|20)\d{2}|等[，,、]?\s*(?:人|发表|报告)")
# 检索口径也可作为「唯一/没人」类断言的依据
SEARCH_PAT = re.compile(r"据(?:我们)?(?:本次)?检索|检索(?:结果|显示|到)|我们检索|本文检索|"
                        r"PubMed|Europe PMC|OpenAlex|标题(?:级|层面)|主题词")
# ① 回指：若前 120 字内已点名（年份 / 期刊 / 「等」），视为同段内正常回指，不报
NAMED_BEFORE = re.compile(r"(?:19|20)\d{2}|等[，,、]|《[^》]+》|\*[A-Z][A-Za-z ]+\*")
# ② 序数用法（第一个假说 / 第一条），非排他性断言
ORDINAL = re.compile(r"^第[一二三四五六七八九十]+(?:个|条|步|类|组|次|阶段|种|层|张|页|项)")
# ② 普通说法（主流软件 / 主流工具），非科学判断
GENERIC_MAINSTREAM = re.compile(r"主流(?:软件|工具|方法|做法|平台|流程|方案)")
# ② 否定语境：句子在否认该断言，而非主张它（「这不等于没人研究过」）
NEGATED = re.compile(r"(?:不等于|并非|不是说|不代表|不能说|并不是|绝非)[^。；！？\n]{0,16}$")
# ② 分组定义用法：「对 X 也无效的」——在定义一类患者，不是下判断
GROUP_DEF = re.compile(r"对[^。，、；：\n]{1,14}(?:也|均|都|同样)?(?:无效|有效|应答|不应答|耐药|敏感)的?$")

# ── ③ 空泛量词 ─────────────────────────────────────────────────
VAGUE = [r"很多", r"一些", r"若干", r"大量", r"部分", r"少数", r"多数", r"许多", r"诸"]
# 后面紧跟数字则不报
NUM_AFTER = re.compile(r"^\s*[（(]?\d")

# ── ④ 缩写：仅匹配「真缩写」，不匹配普通专有名词 ─────────────────
#   三类：① 全大写 2–6 字母（PV / VBM / ENIGMA / GABA）
#         ② 字母+数字（D2 / M1 / M4）
#         ③ 驼峰式（nAChR）
#   用 (?<![-A-Za-z0-9]) 排除连字符内部（避免从 5-HT 里切出 HT）
ABBR = re.compile(
    r"(?<![-A-Za-z0-9])([A-Z]{2,6})(?![-A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])([A-Z]\d[A-Za-z]?)(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])([a-z][A-Z]{2,4}[A-Za-z]?)"
)
# 展开线索：中文全称、括号解释、= 号
EXPANDED = re.compile(r"[（(][^）)]{2,}[）)]|[一-鿿]{2,}[（(]|=|，即|：|（即")
# 跳过：通用词 / 非专业缩写
SKIP = {
    "DOI", "PMID", "URL", "PDF", "PPT", "PPTX", "AI", "IT", "OK", "ID", "vs",
    "Fig", "Table", "et", "al", "No", "Vol", "pp", "SD", "SE", "CI", "OR", "HR",
    "RR", "P", "N", "n", "SPSS", "R", "Python",
}
# 罗马数字/化学式常见误报
FALSE_POS = re.compile(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)$")

# ── ⑤ 数字-口径 ─────────────────────────────────────────────────
NUMERIC = re.compile(r"(\d+(?:\.\d+)?)\s*(%|％|倍|例|人|项|篇|mg|mol|Hz|ms)")


def load_terms(path):
    """术语白名单：{缩写: 建议展开}；无 `=` 则值为空串"""
    terms = {}
    if not path:
        return terms
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    terms[k.strip()] = v.strip()
                else:
                    terms[line] = ""
    except FileNotFoundError:
        print(f"⚠️ 术语白名单不存在：{path}")
    return terms


def split_refs(text):
    """切掉参考文献表，避免"表内条目自证"式的误报"""
    m = re.search(r"^#{1,4}\s*(?:[一二三四五六七八九十]+、)?\s*参考文献", text, re.M)
    return text[:m.start()] if m else text


def nearby(text, start, end, width=40):
    return text[max(0, start - width): min(len(text), end + width)]


def check(text, terms, only):
    hits = {}
    body = split_refs(text)

    # ① 回指——仅报「前 120 字内未点名」者（同段紧邻回指属正常行文）
    if 1 in only:
        out, skipped = [], 0
        for pat in ANAPHORA:
            for m in re.finditer(pat, body):
                prev = body[max(0, m.start() - 120): m.start()]
                if NAMED_BEFORE.search(prev):
                    skipped += 1
                    continue
                line = body[:m.start()].count("\n") + 1
                out.append((line, m.group(), nearby(body, m.start(), m.end(), 28)))
        hits["① 回指词·跨段未点名（引用须自足）"] = out
        if skipped:
            hits["①-附 同段紧邻回指（已跳过）"] = [(0, f"{skipped} 处", "属正常行文，无需改")]

    # ② 排他性断言（硬规则）
    if 2 in only:
        out, skipped = [], []
        for pat in EXCLUSIVE:
            for m in re.finditer(pat, body):
                tok = m.group()
                after = body[m.end(): m.end() + 6]
                prev_frag = body[max(0, m.start() - 24): m.start()]
                # 排除：序数用法 / 普通说法 / 否定语境 / 分组定义
                if (ORDINAL.match(tok)
                        or GENERIC_MAINSTREAM.match(tok + after.lstrip())
                        or NEGATED.search(prev_frag)
                        or GROUP_DEF.search(prev_frag)):
                    skipped.append(tok)
                    continue
                ctx = nearby(body, m.start(), m.end(), 40)
                if not (CITE_PAT.search(ctx) or SEARCH_PAT.search(ctx)):
                    line = body[:m.start()].count("\n") + 1
                    out.append((line, tok, ctx))
        hits["② 排他性断言·未见出处 ⚠️硬规则"] = out
        if skipped:
            hits["②-附 序数/普通说法（已跳过）"] = [(0, f"{len(skipped)} 处", ", ".join(sorted(set(skipped))))]

    # ③ 空泛量词
    if 3 in only:
        out = []
        for pat in VAGUE:
            for m in re.finditer(pat + r"(?=[一-鿿])", body):
                tail = body[m.end(): m.end() + 3]
                if NUM_AFTER.match(tail):
                    continue
                line = body[:m.start()].count("\n") + 1
                out.append((line, m.group(), nearby(body, m.start(), m.end(), 24)))
        hits["③ 空泛量词（建议换具体数）"] = out

    # ④ 缩写首次出现
    if 4 in only:
        out, seen = [], set()
        for m in ABBR.finditer(body):
            tok = m.group(1) or m.group(2) or m.group(3) or ""
            if not tok or tok in seen or tok in SKIP or tok in terms or FALSE_POS.match(tok):
                continue
            seen.add(tok)
            ctx = nearby(body, m.start(), m.end(), 30)
            if not EXPANDED.search(ctx):
                line = body[:m.start()].count("\n") + 1
                out.append((line, tok, ctx))
        hits["④ 缩写首次出现·未见展开"] = out
        if terms:
            known = [t for t in terms if t in seen]
            if known:
                hits["④-附 白名单已跳过"] = [(0, ", ".join(known), "")]

    # ⑤ 数字-口径汇总（仅列出，供人工核）
    if 5 in only:
        out, seen = [], set()
        for m in NUMERIC.finditer(body):
            key = (m.group(1), m.group(2))
            if key in seen:
                continue
            seen.add(key)
            line = body[:m.start()].count("\n") + 1
            out.append((line, f"{m.group(1)}{m.group(2)}", nearby(body, m.start(), m.end(), 26)))
        hits["⑤ 数字-口径（人工核对用）"] = out

    return hits


def main():
    ap = argparse.ArgumentParser(description="文稿内容自检：回指/断言/量词/缩写/数字")
    ap.add_argument("docs", nargs="+", help="待检查的 Markdown 文档")
    ap.add_argument("--terms", help="术语白名单文件（每行一个，可用 KEY=中文全称）")
    ap.add_argument("--only", default="1,2,3,4,5",
                    help="只跑指定检查，逗号分隔（默认 1,2,3,4,5）")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总")
    args = ap.parse_args()

    only = {int(x) for x in args.only.split(",") if x.strip().isdigit()}
    terms = load_terms(args.terms)
    total = 0

    for path in args.docs:
        try:
            text = open(path, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"⚠️ 找不到：{path}\n")
            continue

        print("=" * 92)
        print(f"  检查：{path}   （{len(text.splitlines())} 行）")
        print("=" * 92)

        hits = check(text, terms, only)
        n_doc = 0
        for title, items in hits.items():
            n = len(items)
            n_doc += n
            flag = "🔴" if ("硬规则" in title and n) else ("  " if n else "✅")
            print(f"\n{flag} {title} —— {n} 处")
            if args.quiet or not n:
                continue
            for line, token, ctx in items[:40]:
                loc = f"L{line}" if line else "—"
                print(f"     {loc:>7}  {token:<28} …{ctx.strip()}…")
            if n > 40:
                print(f"     …（另有 {n-40} 处，已截断）")
        total += n_doc
        print(f"\n  小计：{n_doc} 处\n")

    print("=" * 92)
    print(f"  合计 {total} 处。①③④ 为启发式，需人工复核；② 为硬规则，必须补出处。")
    print("  配套清单：`_系统/_流程与工具/内容自检清单.md`")
    print("=" * 92)
    return total


if __name__ == "__main__":
    sys.exit(main())
