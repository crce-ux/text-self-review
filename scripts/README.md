# scripts/

**这里是运行版。正本在 [`research-workflow`](https://github.com/crce-ux/research-workflow) 的 `scripts/`**——开发与测试都在那边。

改脚本请改总仓，再同步过来；**不要只改这里**。

| 脚本 | 干什么 |
|---|---|
| `number_diff.py` | 跨版本（中英 / md↔docx）核对数字是否一致 |
| `check_language.py` | 回指 / 排他性断言 / 空泛量词 / 缩写 / 数字口径 |
| `check_ref_citations.py` | 正文 [n] ↔ 文末编号表 双向核对 |

## 依赖

| 脚本 | 依赖 |
|---|---|
| `check_language.py` · `check_ref_citations.py` | 标准库 |
| `number_diff.py` | Python 3.9+；读 .docx 需 `python-docx`，读 .pdf 需 `pymupdf` |

## 边界

**脚本只做能自动化的那一半。** 命中 ≠ 要改——启发式判据报的是「可疑」，
判断「这句话是不是真的没出处」仍须人工。维度库（`references/dimensions.md`）才是主流程。
