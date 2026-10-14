# scripts/

**这里是运行版。正本在 [`research-workflow`](https://github.com/crce-ux/research-workflow) 的 `scripts/`**——开发与测试都在那边。

改脚本请改总仓，再同步过来；**不要只改这里**。

| 脚本 | 干什么 |
|---|---|
| `convergence_log.py` | **自查轮次记录 → 能不能判收敛**。按 C1a/C1b/C2/C3 判，**回流>0 的轮作废、自动摘出序列**；满 6 轮未收敛报止损 |
| `number_diff.py` | 跨版本（中英 / md↔docx）核对数字是否一致 |
| `check_language.py` | 回指 / 排他性断言 / 空泛量词 / 缩写 / 数字口径 |
| `check_ref_citations.py` | 正文 [n] ↔ 文末编号表 双向核对 |

## 依赖

| 脚本 | 依赖 |
|---|---|
| `check_language.py` · `check_ref_citations.py` · `convergence_log.py` | 标准库 |
| `number_diff.py` | Python 3.9+；读 .docx 需 `python-docx`，读 .pdf 需 `pymupdf` |
| `check_skill_structure.py` | 结构校验（官方 Agent Skills 规范）：name / description / 正文长度 / 深链 / **声明落地** |
| `selfcheck.py` | **一条命令自检**：结构 + 语法 + 依赖。见下 |

## 边界

**脚本只做能自动化的那一半。** 命中 ≠ 要改——启发式判据报的是「可疑」，
判断「这句话是不是真的没出处」仍须人工。维度库（`references/dimensions.md`）才是主流程。

## 自检

```bash
python scripts/selfcheck.py            # 结构 + 语法 + 依赖
python scripts/selfcheck.py --strict   # 结构警告也算失败（CI 用这个）
```

查三样：**结构**（官方规范）· **语法**（逐个编译 `scripts/*.py`）· **依赖**（哪些脚本要装第三方库，只报不判）。
下载本 skill 后想确认「东西是齐的、没坏的」，跑这一条就够。
