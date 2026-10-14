#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_skill_structure.py —— Agent Skill 结构校验器

按官方规范（agentskills.io/specification）校验一个或多个 skill 目录：
可以做 CI 的**静态检查**层——零依赖、不调模型、只读。

【查什么】
  name     ≤64 字符；仅小写字母/数字/连字符；不首尾连字符；不含 `--`；
           **必须与父目录名一致**；不得含保留词 `anthropic` / `claude`
  desc     存在、非空、≤1024 字符
  frontmatter 只允许白名单字段（多写的会被静默忽略，属噪音）
  正文     建议 < 500 行（超了应拆到 references/）
  引用     只允许从 SKILL.md 往下一层（禁止 `references/a/b.md` 这类深链）
  目录     有 references/ 或 scripts/ 时，SKILL.md 里应能索引到
  Anti-Patterns  建议存在，且条目应是**可判定禁令**而非形容词
  声明落地 SKILL.md / README.md 里写到的 `scripts/x.py`、`references/y.md` 必须真实存在
           （**「声明落地」规则实际抓到过 bug**：文档声明了 `verify_pmid_doi.py`，分发时漏了对应文件）

【用法】
    python check_skill_structure.py <skill目录> [<skill目录> ...]
    python check_skill_structure.py --root <含多个 skill 的目录>
    python check_skill_structure.py <目录> --strict    # 警告也当失败

【退出码】
    0  全部通过
    1  有错误
    2  仅 --strict 下有警告
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 官方规范允许的 frontmatter 字段
ALLOWED_FIELDS = {"name", "description", "license", "compatibility",
                  "metadata", "allowed-tools"}
RESERVED_WORDS = ("anthropic", "claude")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESC = 1024
MAX_BODY_LINES = 500

# 形容词式禁令（不易判定）——出现在 Anti-Patterns 里应改成具体禁令
VAGUE_BAN = re.compile(r"不要(写|做)得(太)?(差|烂|水|随便)|写得不好|质量要高")


def parse_frontmatter(text: str):
    """返回 (fields: dict, body: str, error)。只支持顶层标量字段。"""
    if not text.startswith("---"):
        return {}, text, "SKILL.md 必须以 YAML frontmatter 开头（---）"
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}, text, "frontmatter 未正确闭合（缺少第二个 ---）"
    raw, body = m.group(1), text[m.end():]
    fields = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":          # 嵌套（如 metadata: 的子项）——跳过
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fields[k.strip()] = v.strip()
    return fields, body, None


def check_skill(d: Path, strict: bool) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    skill_md = d / "SKILL.md"

    if not skill_md.is_file():
        return [f"{d.name}: 缺 SKILL.md"], []

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fields, body, err = parse_frontmatter(text)
    if err:
        errs.append(f"{d.name}: {err}")
        return errs, warns

    # ── name ─────────────────────────────────────────────
    name = fields.get("name", "")
    if not name:
        errs.append(f"{d.name}: frontmatter 缺 name")
    else:
        if len(name) > MAX_NAME:
            errs.append(f"{d.name}: name 超过 {MAX_NAME} 字符（{len(name)}）")
        if not NAME_RE.match(name):
            errs.append(f"{d.name}: name 只能是小写字母/数字/连字符，且不以连字符开头结尾、不含连续连字符：{name!r}")
        if name != d.name:
            errs.append(f"{d.name}: name（{name!r}）与目录名不一致")
        low = name.lower()
        for rw in RESERVED_WORDS:
            if rw in low:
                errs.append(f"{d.name}: name 含保留词 {rw!r}")

    # ── description ──────────────────────────────────────
    desc = fields.get("description", "")
    if not desc:
        errs.append(f"{d.name}: frontmatter 缺 description")
    elif len(desc) > MAX_DESC:
        errs.append(f"{d.name}: description 超过 {MAX_DESC} 字符（{len(desc)}）")

    # ── 白名单字段 ────────────────────────────────────────
    extra = set(fields) - ALLOWED_FIELDS
    if extra:
        warns.append(f"{d.name}: frontmatter 含非规范字段 {sorted(extra)}（会被静默忽略）")

    # ── 正文长度 ──────────────────────────────────────────
    n_lines = body.count("\n") + 1
    if n_lines > MAX_BODY_LINES:
        errs.append(f"{d.name}: 正文 {n_lines} 行，超过 {MAX_BODY_LINES} 行——拆到 references/")

    # ── 引用只走一层 ──────────────────────────────────────
    for ref in re.findall(r"`(references/[^`]+)`", body):
        # ⚠️ 占位符不是路径（如 `references/cards/<slug>.md`）——它在讲命名格式，
        #    不是深链。与「声明落地」同一条判据，两处都要豁免，否则同一类误报漏一处。
        if any(c in ref for c in "<>*?{}"):
            continue
        # 只对**文件**判深链——`references/cards/` 是目录提及，不是深链。
        if not re.search(r"\.\w+$", ref):
            continue
        if ref.count("/") > 1:
            errs.append(f"{d.name}: 深链引用 {ref}（规范只允许从 SKILL.md 往下一层）")

    # ── 子目录说明 ────────────────────────────────────────
    for sub in ("references", "scripts", "assets"):
        if (d / sub).is_dir() and sub not in body:
            warns.append(f"{d.name}: 存在 {sub}/ 但 SKILL.md 正文未提及")

    # ── Anti-Patterns ─────────────────────────────────────
    if "Anti-Patterns" not in body and "反模式" not in body:
        warns.append(f"{d.name}: 建议加 `## Anti-Patterns` 段（用可判定的禁令）")
    else:
        seg = re.split(r"##\s*(?:Anti-Patterns|反模式)[^\n]*\n", body, maxsplit=1)
        if len(seg) > 1 and VAGUE_BAN.search(seg[1][:2000]):
            warns.append(f"{d.name}: Anti-Patterns 里有形容词式禁令——改成可判定的具体禁令")

    # ── 声明落地：文档里写到的文件必须真实存在 ────────────
    # ⚠️ 「声明落地」这项抓到过真 bug：README 声明了 `verify_pmid_doi.py`，分发时却漏了对应文件，
    #    文档与实物对不上，用户按文档找会扑空。所以归为**错误**而非警告。
    declared = set()
    for doc in ("SKILL.md", "README.md", "scripts/README.md", "references/README.md"):
        f = d / doc
        if not f.is_file():
            continue
        for m in re.finditer(r"`((?:scripts|references|assets)/[^`\s]+?\.(?:py|sh|md|json|ya?ml))`",
                             f.read_text(encoding="utf-8", errors="replace")):
            rel = m.group(1)
            # 占位符不是真路径（如 `references/cards/<slug>.md`），跳过——
            # 否则会把「文档在讲命名格式」误判成「文件缺失」。
            if any(c in rel for c in "<>*?{}"):
                continue
            declared.add((doc, rel))
    for doc, rel in sorted(declared):
        if not (d / rel).is_file():
            errs.append(f"{d.name}: {doc} 声明了 `{rel}`，但该文件不存在")

    return errs, warns


def skill_dirs(root):
    """找到所有 skill 目录。

    两类：
    ① 库根下的**直接子目录**里带 SKILL.md 的——独立的 skill 仓；
    ② 各仓 `skills/<名字>/` 里带 SKILL.md 的——**总仓内嵌的 skill 包**。

    ⚠️ **只下探一层**。再深就分不清「skill 包」与「skill 里引用的示例目录」了。
    """
    out = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if (p / "SKILL.md").is_file():
            out.append(p)
            continue
        pack = p / "skills"
        if pack.is_dir():
            out += [q for q in sorted(pack.iterdir())
                    if q.is_dir() and (q / "SKILL.md").is_file()]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Agent Skill 结构校验器")
    ap.add_argument("dirs", nargs="*", help="skill 目录")
    ap.add_argument("--root", help="含多个 skill 子目录的父目录")
    ap.add_argument("--strict", action="store_true", help="警告也当失败")
    a = ap.parse_args()

    targets = [Path(x) for x in a.dirs]
    if a.root:
        targets += skill_dirs(Path(a.root))
    if not targets:
        print("没有可校验的目录")
        raise SystemExit(1)

    all_errs, all_warns = [], []
    for d in targets:
        if not d.is_dir():
            all_errs.append(f"{d}: 目录不存在")
            continue
        e, w = check_skill(d, a.strict)
        all_errs += e
        all_warns += w
        status = "OK " if not e else "FAIL"
        print(f"  [{status}] {d.name:<24} 错误 {len(e)} · 警告 {len(w)}")
        for msg in e:
            print(f"        ✗ {msg}")
        for msg in w:
            print(f"        ! {msg}")

    print()
    print(f"汇总：{len(targets)} 个 skill · 错误 {len(all_errs)} · 警告 {len(all_warns)}")
    if all_errs:
        raise SystemExit(1)
    if all_warns and a.strict:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
