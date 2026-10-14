#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨版本数字一致性比对（维度 D15）。

用途：同一份文本的多版本（中文 vs 英文、md vs docx、初稿 vs 终稿）
      之间的数字必须逐条对应。本脚本提取两版的数字集合求差集，
      把「一处有、另一处没有」的数字连同上文一起打出来。

用法：
    python number_diff.py <文件A> <文件B> [--window 40]

支持 .txt / .md / .docx / .pdf。docx 需 python-docx；pdf 需 pymupdf。

注意：本脚本是**辅助**工具，不是判据。
      数字对不上是「需要人工回去看」，不一定就是错——
      版本间本就可以合法地增删数字。它能做的是把范围从「整篇」缩到「几处」。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

# Windows 控制台默认 GBK，中文与符号会抛 UnicodeEncodeError——强制 UTF-8 输出
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 匹配整数、小数、百分比、千分位、科学计数
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*(?:\s?[%％])?")


def read_text(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".markdown"):
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError:
            sys.exit("需要 python-docx：pip install python-docx")
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.extend(cell.text for cell in row.cells)
        return "\n".join(parts)
    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError:
            sys.exit("需要 pymupdf：pip install pymupdf")
        with fitz.open(str(path)) as pdf:
            return "\n".join(page.get_text() for page in pdf)
    sys.exit(f"不支持的格式：{suffix}（支持 .txt/.md/.docx/.pdf）")


def normalise(tok: str) -> str:
    """把 1,234 / 1.234 / 12% 之类的写法归一，便于跨语言比对。"""
    t = tok.strip().replace(" ", "")
    t = t.replace("％", "%")
    # 千分位 or 小数点：统一去掉分隔符，但保留小数点语义
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", t.rstrip("%")):
        t = t.replace(",", "").replace(".", "")
    else:
        t = t.replace(",", ".")
    return t


def collect(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for m in NUM_RE.finditer(text):
        raw = m.group(0)
        key = normalise(raw)
        if not key or key in ("0",):
            continue
        start = max(0, m.start() - 60)
        ctx = " ".join(text[start:m.end() + 60].split())
        out.setdefault(key, []).append(ctx)
    return out


def report(label: str, keys: list[str], pool: dict[str, list[str]], window: int) -> None:
    if not keys:
        print(f"\n  {label}：无")
        return
    print(f"\n  {label}（{len(keys)} 个）：")
    for k in sorted(keys):
        ctx = pool[k][0]
        print(f"    {k:<12} … {ctx[:window * 2]} …")


def main() -> None:
    ap = argparse.ArgumentParser(description="跨版本数字一致性比对")
    ap.add_argument("file_a")
    ap.add_argument("file_b")
    ap.add_argument("--window", type=int, default=40, help="上下文宽度（默认 40）")
    args = ap.parse_args()

    a, b = pathlib.Path(args.file_a), pathlib.Path(args.file_b)
    for p in (a, b):
        if not p.exists():
            sys.exit(f"文件不存在：{p}")

    na, nb = collect(read_text(a)), collect(read_text(b))
    only_a = [k for k in na if k not in nb]
    only_b = [k for k in nb if k not in na]
    both = [k for k in na if k in nb]

    print(f"A = {a.name}   数字 {len(na)} 种")
    print(f"B = {b.name}   数字 {len(nb)} 种")
    print(f"共有 {len(both)} 种｜仅 A 有 {len(only_a)} 种｜仅 B 有 {len(only_b)} 种")

    report("[仅 A 有]", only_a, na, args.window)
    report("[仅 B 有]", only_b, nb, args.window)

    if not only_a and not only_b:
        print("\n[OK] 两版数字集合完全一致。")
        print("   （注意：数字集合一致只说明数字没漏，不说明口径一致——口径仍需人工过 D1。）")


if __name__ == "__main__":
    main()
