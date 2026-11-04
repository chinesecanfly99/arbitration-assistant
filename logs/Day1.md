# Day 1 日志（2026-11-04）

模板：每一步写「目标 → 实测 → 证据」，实测必须是跑出来的数字，不是"应该可以"。

## S0.1 锁定城市与案由清单

- 目标：定一个城市，列 12 类可仲裁案由 + 3 类必须指路的事项。
- 实测：`config/city.json` 写入 city=深圳；`docs/causes.md` 列 12 类案由（每类带依据条号、证据清单、对应计算函数）+ 3 类指路项（工伤认定/社保补缴/公积金）。
- 待办：社平工资 `social_avg_wage` 仍为 null，未联网核实前"3 倍封顶"只给 warning 不计算。
- 证据：`config/city.json`、`docs/causes.md`

## S0.3 领域 schema

- 目标：前后端共用一套字段定义，避免并行开发打架。
- 实测：`schema.json` 定义 9 个业务字段（含类型与 enum：解除方式 legal_termination / illegal_dismissal / resignation / contract_expiry）。
- 证据：`schema.json`

## S1.1–S1.7 规则内核

- 目标：工龄折算、N、2N、二倍工资、加班费、未休年假、欠薪与总计，全部纯函数 + 单元测试。
- 实测：`PYTHONPATH=.libs python -m pytest` → **89 passed in 0.18s**（规则部分 72 条 + 法条 17 条）。
- 过程中修掉的真 bug：`severance_months_by_law` 用 `divmod(months, 12)` 且整除时返回 `years + 0.5`，导致**正好 12 个月工龄被算成 1.5 个月补偿**。改成 `rest == 0 → float(years)`，并补了 12/24/36 个月三条回归用例。
- 证据：`tests/test_tenure.py` 等 7 个文件

## S1.8 时效倒计时

- 目标：1 年仲裁时效，区分四类起算点，欠薪在劳动关系存续期间不适用时效。
- 实测：`deadline.analyze()` 返回 5 项，剩余 ≤30 天标记 urgent；欠薪 `applicable=False` 并附条款说明。
- 证据：`src/arb/deadline.py`、`tests/test_deadline.py`

## 🚦 G1 门禁：规则内核

- 目标：核心模块覆盖率 ≥90%，所有规则有单测。
- 实测：`--cov=arb` → TOTAL **97%**（calc 99%、deadline 100%、laws 93%、dates 92%）。
- 结论：**G1 通过**。
- 证据：下方覆盖率输出

```
Name                  Stmts   Miss  Cover
src\arb\calc.py         168      1    99%
src\arb\deadline.py      57      0   100%
src\arb\laws.py         160     11    93%
src\arb\dates.py         24      2    92%
TOTAL                   412     14    97%
```

## S2.1 抓取法条原文（含改道记录）

- 目标：入库 8 部法条原文，带生效日期。
- 实测（第一次尝试失败）：python 直连 flk.npc.gov.cn / www.gov.cn / www.npc.gov.cn，DNS 通但 HTTPS 一律报
  `URLError <urlopen error [Errno 2] No such file or directory>`；同一台机器访问 pypi.org、raw.githubusercontent.com 正常 → 判定为站点侧不可达，不是我们的代码问题。
- 改道：GitHub `LawRefBook/Laws`（5172 个文件，Markdown 原文，含版本日期）。`python -m scripts.fetch_laws` 落 6 部：
  - 劳动合同法 98 条（2012-12-28）—— 与官方公布条数一致
  - 劳动争议调解仲裁法 54 条（2007-12-29）
  - 劳动法 107 条（2018-12-29）
  - 职工带薪年休假条例 10 条（2007-12-14）
  - 企业职工带薪年休假实施办法 19 条（2008-07-17）
  - 社会保险法 98 条（2018-12-29）
- 人工抽查：劳动合同法第 10/47/82/87 条正文与官方一字不差。
- 未完成：8 部里还差 2 部（劳动合同法实施条例、深圳地方口径），明日补。
- 证据：`scripts/fetch_laws.py`、`data/laws/*.jsonl`

## S2.2 清洗与入库

- 实测：`scripts/fetch_laws.py --check` 自检通过；每条统一字段 `law/slug/version_date/article_no/article_idx/text/source_repo/source_path/source_url/fetched_at`。
- 发现并修正的建模错误：`article_idx` 是**源文件里的位置**（第一条 = 2），不是条号。第一版 `laws.get(slug, idx)` 直接拿它当条号查，导致 `get("labor_contract_law", 47)` 返回 None、反例测试全部"通过"（假通过）。已改为按 `Article.num`（由 `article_no` 解析）查。
- 证据：`src/arb/laws.py:get()`

## S2.4 检索接口

- 目标：口语问题能召回到正确条号。
- 实测：bigram + IDF 加权（未上 BM25/向量，30 条规模不需要）。加"口语→法条用词"扩展表后：
  - "公司没签书面劳动合同能要双倍工资吗" → 第 82 条（0.814，top1）
  - "被辞退后多久内要去申请劳动仲裁" → 仲裁法第 27 条（0.599，top1）
  - "经济补偿的年限怎么算" → 第 47 条（1.0，top1）
  - "没休的年假怎么补偿" → 年休假条例第 5 条（0.608，top1）
- 教训：不加扩展表时四条查询**全部召回失败**（第一版用纯 bigram 覆盖率，长条文占便宜）。用户说"年限"，法条写"工作年限"——检索层必须有口语映射，这就是产品里"关键词芯片"的技术原型。
- 证据：`src/arb/laws.py:search()`、`EXPAND`

## S2.5 反例库

- 目标：伪造法条必须被拦住，且要能量化"拦住多少"。
- 实测：`data/negative_laws.jsonl` 20 条，三类构造（条号越界 / 整部法编造 / 条号真但内容篡改）。
  第一层确定性校验拦住 **19/20**；漏网的 1 条是 neg-12——原文"六个月以上不满一年按一年计算"被反写成"按半个月计算"，**每个词都在原文里**，bigram 支持度 0.85，比正常改写（0.68–0.78）还高。
- 结论：`support` 只能当"是否抄自原文"的信号，不能当"内容是否正确"的判据；语义裁决必须做第二层（模型读原文核对关系）。已把 neg-12 写成显式的 `LAYER1_BLIND_SPOTS`，避免团队误以为已经解决。
- 证据：`tests/test_laws.py::test_negative_layer1_rejected`

## 今日结论

- G1 门禁**通过**（覆盖率 97%）；G2 未通过（案例库 0/50）。
- 明天：补 2 部法条 + 50 条案例库骨架 → S3.1 故事→参数抽取。
- 未解决的外部依赖：深圳社平工资口径（需联网核实）、真实用户访谈（尚未约到）。
