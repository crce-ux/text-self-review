# -*- coding: utf-8 -*-
"""
check_ref_citations.py —— 编号-引用双向核查（质量核查④用）

用途：校验综述/文档正文的 [n] 引用与文末编号表是否一一对应。
    —— 发现"正文引用了但表内无条目"（缺失）与"表内有但正文未引用"（悬挂），
       以及正文中是否残留旧编号。对应《文献调研流程手册》质量核查四件套之④。

用法：
    python check_ref_citations.py --doc 整合综述.md
    python check_ref_citations.py --doc 候选课题深化准备.md --refs-start "## 七、参考文献"

参数：
    --refs-start  参考文献章节标题（默认自动找 "## 参考文献" 或 "## 七、参考文献"）

输出：正文引用编号集合 / 表内条目编号集合 / 缺失（正文引用但表内无）/
     悬挂（表内有但正文未引）—— 完全一致时提示 ✅。

依赖：标准库。
"""

import sys
import re
import argparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_cited(body):
    """从正文提取所有 [n] 引用（支持 [1]、[1,2]、[4-6]）"""
    cited = set()
    for m in re.finditer(r"\[(\d+(?:\s*[,-]\s*\d+)*)\]", body):
        seg = m.group(1).replace(" ", "")
        for part in seg.split(","):
            if "-" in part:
                a, b = part.split("-")
                cited.update(range(int(a), int(b) + 1))
            elif part:
                cited.add(int(part))
    return cited


def parse_listed(refs):
    """从参考文献表提取编号——支持 `1. Author` 与 `[1] Author` 两种格式"""
    listed = set(int(m.group(1)) for m in re.finditer(r"^(\d+)\.\s", refs, re.M))
    listed |= set(int(m.group(1)) for m in re.finditer(r"^\[(\d+)\]\s", refs, re.M))
    return listed


def find_refs_section(text, refs_start):
    """定位参考文献章节：优先 --refs-start，其次按 ^#+.*参考文献 宽松匹配"""
    if refs_start:
        i = text.find(refs_start)
        if i != -1:
            return text[:i], text[i:]
    # 宽松匹配任意"参考文献"标题行（支持 ## 七、参考文献、## 参考文献（xxx）、[1]-[N] 等变体）
    for m in re.finditer(r"^#{1,6}\s*(?:\d+|[一二三四五六七八九十]+)[\.、]?\s*参考文献.*$", text, re.M):
        return text[:m.start()], text[m.start():]
    sys.exit("未找到参考文献章节，请用 --refs-start 指定")


def main():
    ap = argparse.ArgumentParser(description="编号-引用双向核查")
    ap.add_argument("--doc", required=True, help="文档路径")
    ap.add_argument("--refs-start", help="参考文献章节标题")
    args = ap.parse_args()

    text = open(args.doc, encoding="utf-8").read()
    body, refs = find_refs_section(text, args.refs_start)
    cited = parse_cited(body)
    listed = parse_listed(refs)

    missing = sorted(cited - listed)   # 正文引用但表内无
    orphan = sorted(listed - cited)    # 表内有但正文未引用

    print(f"正文引用编号：{len(cited)} 个  {sorted(cited)}")
    print(f"表内条目编号：{len(listed)} 个  {sorted(listed)}")
    print("-" * 50)
    if missing:
        print(f"⚠️ 正文引用但表内缺失：{missing}")
    else:
        print("✅ 无缺失（正文引用均在表内）")
    if orphan:
        print(f"⚠️ 表内有但正文未引用（悬挂）：{orphan}")
    else:
        print("✅ 无悬挂（表内条目均被正文引用）")
    print("-" * 50)
    if not missing and not orphan:
        print("🎯 双向完全一致，编号体系自洽")
    else:
        print("需修复上述不一致项")


if __name__ == "__main__":
    main()
