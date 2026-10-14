#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selfcheck.py —— skill 自检：结构 + 语法 + 声明落地

【给谁用】
    拿到这个 skill 的人。一条命令确认「东西是齐的、没坏的」。

【查三样】
    1. 结构       —— 调同目录的 `check_skill_structure.py`（官方规范：name / description /
                     正文长度 / 深链 / 声明落地 / Anti-Patterns）
    2. 语法       —— 逐个编译 `scripts/*.py`，捕获 syntax error
    3. 依赖       —— 报告哪些脚本需要第三方库（**只报不判**：不装也能用其余部分）

【用法】
    python scripts/selfcheck.py            # 在 skill 根目录跑
    python scripts/selfcheck.py --strict   # 结构警告也算失败

【退出码】
    0  全过
    1  有问题
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import pathlib
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CHECKER = HERE / "check_skill_structure.py"

# 常见第三方依赖名 → pip 包名
PIP_NAME = {
    "docx": "python-docx", "fitz": "pymupdf", "PIL": "Pillow",
    "openpyxl": "openpyxl", "DrissionPage": "DrissionPage",
    "win32com": "pywin32", "pptx": "python-pptx",
}
STDLIB = set(sys.stdlib_module_names)


def check_structure(strict: bool) -> int:
    if not CHECKER.is_file():
        print(f"  ✗ 找不到 {CHECKER.name}——skill 不完整")
        return 1
    cmd = [sys.executable, str(CHECKER), str(ROOT)]
    if strict:
        cmd.append("--strict")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.splitlines():
        if line.strip() and not line.startswith("check_skill") and "汇总" not in line:
            print(f"    {line.strip()}")
    return r.returncode


def check_syntax() -> int:
    bad = 0
    for p in sorted(HERE.glob("*.py")):
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=str(p))
        except SyntaxError as e:
            print(f"    ✗ {p.name}:{e.lineno} 语法错误：{e.msg}")
            bad += 1
    if not bad:
        n = len(list(HERE.glob("*.py")))
        print(f"    ✅ {n} 个脚本语法通过")
    return bad


def check_deps() -> None:
    """报告脚本需要哪些第三方库。

    ⚠️ 用 `find_spec` 而不是 `__import__`——**导入会执行模块顶层代码**。
    实测踩过：`fetch_journal_metrics.py` 一导入就跑出「找不到期刊数据目录」并报错，
    `ppt_kit` / `ppt_style` 这类**同目录的兄弟模块**还被当成 pip 包，
    给出「pip install ppt_kit」这种不存在的建议。三个问题都由此而来。
    """
    local = {p.stem for p in HERE.glob("*.py")}       # 同目录兄弟模块，不是 pip 包
    need: dict[str, set[str]] = {}
    for p in sorted(HERE.glob("*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split(".")[0]]
            for m in mods:
                if m in STDLIB or m == "__future__" or m in local:
                    continue
                need.setdefault(m, set()).add(p.name)
    if not need:
        print("    全部只用标准库")
        return
    for m in sorted(need):
        try:
            installed = importlib.util.find_spec(m) is not None
        except (ImportError, ValueError):
            installed = False
        mark = "已装" if installed else "未装"
        pip = PIP_NAME.get(m, m)
        print(f"    {mark}  {m:<14} → pip install {pip}   （{', '.join(sorted(need[m]))}）")


def main() -> int:
    ap = argparse.ArgumentParser(description="skill 自检")
    ap.add_argument("--strict", action="store_true", help="结构警告也算失败")
    a = ap.parse_args()

    print(f"selfcheck · {ROOT.name}")
    print("\n  ── 1 结构 ──")
    struct = check_structure(a.strict)
    print("\n  ── 2 语法 ──")
    syn = check_syntax()
    print("\n  ── 3 依赖（只报不判）──")
    check_deps()

    bad = struct + syn
    print()
    if bad:
        print(f"  ❌ {bad} 处问题")
    else:
        print("  ✅ 全过")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
