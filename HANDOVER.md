# 交接文档（HANDOVER）

## 2026-11-07 接续交付

- 交付包补齐离线测试依赖和打包脚本。解压后可运行 `python run_tests.py`，本轮隔离环境复验 368 条通过，使用开发依赖测得覆盖率 92%。
- 首批 7 条公开类案已接入网页、网页版打印和 Markdown 报告。案例与评测数据分开存放，评测仍为金额 50/50、法条引用 84/84。
- 最新验收状态以 [执行计划与验收清单](docs/执行计划与验收清单.md) 和 [G1 复核记录](logs/G1_gate.md) 为准。五案独立手算、真人测试、人工红线复核、视频和彩排待完成。

以下为原交接记录，供追溯项目设计和基线。

> 给接手的同学，或者另一个 AI（如 GPT）。
> 目标：**不读全部代码，也能在 30 分钟内跑起来、知道哪些地方不能碰、知道下一步做什么。**
>
> 本文所有数字都可用文中命令当场复验。写文档的人没有编数——若你发现某个数字对不上，
> 说明代码已经变了，先跑一遍命令再信本文。

---

## 0. 三十秒版

| 项 | 值 |
|---|---|
| 项目 | 劳动仲裁维权助手：一段大白话 → 能不能申请 / 能要多少钱 / 带什么材料 / 去哪立案 / 值不值得去 |
| 形态 | 纯 Python 标准库单体应用，零第三方依赖，零联网，零 API key |
| 仓库 | <https://github.com/chinesecanfly99/arbitration-assistant>（远端已是 `cfe31b7`） |
| 代码量 | `src/arb/` 25 个模块，约 5,200 行；`tests/` 30 个文件 |
| 测试 | **364 passed**，覆盖率 **92%**（`python run_tests.py`） |
| 一条命令启动 | `python run.py`（自动加 `sys.path`、端口被占自动换、打开浏览器） |
| 核心卖点 | 钱和时效是**纯规则**算的，可复算；每条结论都挂法条原文，可逐条回库核对 |
| 当前阶段 | 功能闭环完成；**差真人测试、演示视频、彩排**（见 §8） |

**一句话记住它的取舍**：能算的绝不让模型算，能引的绝不自己写，算不了的就说不算。

---

## 1. 怎么把这份文档交给 GPT

推荐做法（按可靠性排序）：

1. **给仓库访问**：把 GitHub 仓库链接或克隆下来的目录交给它，让它自己读；本文当索引。
2. **给压缩包**：`python -m scripts.make_zip` 生成 `劳动仲裁维权助手_交付包.zip`
   （244 项 / 890 KB，含 `vendor/`、五城数据、本文），连同本文一起上传。
3. **只贴文字**：至少贴本文 + `README.md` + `src/arb/pipeline.py`。信息会不够，容易改错。

开场提示词可以直接用这段：

```text
这是一个纯 Python 标准库的劳动争议仲裁测算项目，364 个测试全绿。请先读 HANDOVER.md，
再跑 `python run_tests.py` 确认基线。之后任何改动都必须满足：测试全绿、
`python -m scripts.eval_report` 的金额命中与引用核验不下降、不引入第三方依赖。
改完请说明你动了哪个文件、为什么、以及你怎么验证的。
```

---

## 2. 环境与运行（先跑通再谈改动）

```powershell
# 一条命令启动（推荐）
python run.py                    # → http://127.0.0.1:8765

# 跑测试（零安装：pytest 随仓库携带，在 vendor/pkgs/）
python run_tests.py              # → 364 passed

# 命令行测算
$env:PYTHONPATH = "src"
python -m arb.cli "2020年3月1日入职，月薪9000，一直没签书面合同。2024年5月20日主管口头说不要我了，还有5天年假没休。"

# 三屏演示（录视频用，日期固定为 2024-06-01，合计恒为 184,137.93）
python -m arb.demo

# 导出 PDF
python -m arb.pdf "同一句话" -o 报告.pdf
```

| 项 | 要求 |
|---|---|
| Python | 3.10+（CI 覆盖 3.10 / 3.12；本机开发用 3.11） |
| 第三方包 | **不需要**。`requirements.txt` 只有 pytest（测试用） |
| 网络 | **不需要**。法条、案例、城市口径都是本地 `data/` 下的 JSON/JSONL |
| API key | **不需要**。`llm.py` 可选，无 key 时全走规则 |
| 数据库 | 无。无会话、无持久化 |

三个平台都要能跑。已处理的跨平台点：输出编码（`console.py`）、端口占用（`run.py`）、
路径分隔符（`make_zip.py`）、写死盘符（`tests/test_console.py` 扫源码禁止）。

---

## 3. 代码地图（按"你为什么要打开它"排序）

```
src/arb/
  pipeline.py    ★ 主入口。analyze() 把下面所有东西串起来，返回一个 dict
  calc.py        ★ 计算内核：N / 2N / 二倍工资 / 加班费 / 年假 / 欠薪 / 汇总（不调模型）
  deadline.py    ★ 时效内核：1 年时效、起算点、欠薪例外、中断重算
  scope.py       受案范围判定 + 红线拒答（工伤/社保/公积金指路；索要胜诉率拒绝）
  gates.py       ★ 三层闸门：受案范围 → 资格（一事不再理/跨城市/退休/实习/时效）→ 口径
  city.py        ★ 城市口径库（读 data/city/*.json）
  worth.py       ★ 六维值得性打分 + 三选一结论
  venue.py       ★ 立案路径（仲裁/网申/起诉/撤销/监察/法律援助）
  materials.py   ★ 材料清单 + 谁举证 + 去哪开
  evidence.py    证据强度打分 + "谁举证"名单
  laws.py        ★ 法条库：加载/条号核验/IDF 检索/引用支持度/反幻觉校验
  extract.py     规则抽取：一段话 → 9 个字段（抽不到就留空，不猜）
  llm.py         可选模型层（只抽字段；读数默认不进计算）
  map.py         案件完整度地图（10 格）
  mock_hr.py     抗辩预演（扮 HR 三轮）
  chips.py       35 个法律术语芯片
  application.py 仲裁申请书草稿
  web.py         ★ 单页前端（stdlib http.server）+ 各导出路由
  cli.py         命令行渲染（Markdown）
  pdf.py         手写 PDF 生成器（STSong-Light，不嵌字体）
  demo.py        三屏演示
  console.py     输出编码兜底
  dates.py / evalkit.py / __init__.py
```

**关键函数签名**（改之前先看签名，别猜）：

```python
pipeline.analyze(story, today=None, hints=None, confirmed=(), mode="strict", city=None) -> dict
#   status ∈ {"ok", "need_more", "out_of_scope", "blocked"}
#   返回键：status/fields/sources/pending/assumptions/scope/gates/items/total/deadlines/
#           evidence_score/materials/venue/worth/one_final_note/rehearsal/questions

calc.compute(inp: ClaimInput, policy: Policy | None = None) -> dict
#   {"items": [...], "total": float, "service_months", "service_years", "severance_months", "warnings"}

gates.qualify(story, fields=None, verdict=None, today=None, city=None) -> dict
#   {"status","can_arbitrate","blockers","warnings","layers","cites","city","city_name","cities_seen"}

worth.compute(fields, total, types=None, evidence=None, city=None, days_left=None) -> dict
venue.build(city=None, days_left=None, total=None) -> list[dict]
materials.build_materials(types, story="") -> list[dict]
materials.dispute_types(causes, items=None) -> set[str]
evidence.score(have: set[str], types=None) -> dict
laws.get(slug, num) / laws.exists(slug, "第47条") / laws.resolve_name("《劳动合同法》") / laws.search(q, k=5)
city.get("深圳") / city.normalize("鹏城") / city.table()
scope.judge(story, fields=None) -> Verdict(in_scope, cause, causes, redirect, refusal_reason, hints)
```

---

## 4. 五条硬约束（违反任何一条，项目就变成另一个东西）

这五条是产品的**全部价值**，代码里都有测试兜着。改代码前先读，不要"优化"掉。

### 4.1 钱只能由 `calc.py` 算
模型可以抽字段，**绝不能算金额**。
- 校验：`tests/test_citations.py`、`tests/test_nocontract.py`、`tests/test_severance.py` 等把每个数字钉死
- 后果：让模型参与算术，`184,137.93` 这类数字立刻不可复现，整个"可核验"卖点失效

### 4.2 引用只能来自 `data/laws/`
任何输出里的法条必须先 `laws.exists(slug, 条号)` 过关。
- 新增引用 → `pipeline.basis_cites_ok()` 会校验；不过关的条号在 UI 上标"引用异常"
- 反例库 `data/negative_laws.jsonl` 20 条专测这个（19/20 被拦，1 条是已知语义盲区 `neg-12`）

### 4.3 未确认的读数不进计算
模型/图片读出来的字段先放 `pending`，用户点头（`confirmed`）之后才写进 `fields`。
口述与读数冲突时**两个值都摆出来，不擅自择一**。
- 实现：`pipeline.merge_hints()`
- 测试：`tests/test_confirm.py`
- 注意：规则抽取对没提到的数值字段会给 `0`（占位），判"有没有说过"时必须把 `0` 当没说（`pipeline._absent()`）

### 4.4 闸门判 `fail` 时不许出金额
一事不再理、已签和解协议等情形返回 `status="blocked"`，**不返回 total**。
- 测试：`tests/test_city_gates.py::test_res_judicata_blocks_calculation`
- 理由写进 README 了：一个看起来确定的总数，比"算不出来"危险得多

### 4.5 覆盖不到的城市不许套数字
五城（京/沪/广/深/杭）各有独立 JSON；其它城市**明说"未覆盖"**，3 倍封顶按未启用处理。
- 实现：`gates.detect_city()` + `pipeline.analyze()` 的 `elif gates.get("city_name") and not city_info` 分支
- 测试：`tests/test_city_gates.py::test_uncovered_city_says_so_and_does_not_borrow_numbers`

---

## 5. 数据契约（要加数据时看这里）

| 数据 | 路径 | 结构要点 | 怎么加 |
|---|---|---|---|
| 法条 | `data/laws/<slug>.jsonl` | `{law, slug, version_date, article_no, article_idx, text, source_url}` 一行一条 | 加文件 **且** 改 `laws.LAW_ORDER` + `laws.SHORT_NAME` + `laws.ALIASES`，否则 `resolve_name` 找不到、`test_citations` 会红 |
| 司法解释 | `data/laws/sfjs1.jsonl`、`sfjs2.jsonl` | 同上，slug 为 `sfjs1`/`sfjs2` | 已入库：解释（一）54 条、解释（二）21 条 |
| 城市 | `data/city/<city>.json` | `city/province/aliases/verified_at/verify_required/params{sources,notes}/arbitration{http, online, hotlines}` | **只加文件即可**，`city.load_all()` 自动扫目录；`params` 必须含 `min_wage_monthly`、`avg_wage_monthly` |
| 评测集 | `data/cases.jsonl` | `{id,cause,hardness,title,story,gold,must_cite,expected,source}` | 加行即可；`gold` 是金标准字段，`expected` 用于金额比对 |
| 反例 | `data/negative_laws.jsonl` | `{id,slug,article_no,fake_claim}` | 加行即可，`tests/test_laws.py` 统计拦截率（改数量要同步测试里的 19/20 断言） |
| 字段定义 | `schema.json` | JSON Schema Draft-07 | 改字段名先改这里；`tests/test_schema.py` 强制它与 `calc.ClaimInput` 一一对应 |

> ⚠️ `laws.load_all()` 和 `city.load_all()` 都带 `functools.lru_cache`。
> 测试里动态造数据要 `load_all.cache_clear()`，否则读到旧结果。

当前规模：**10 部 / 519 条**法条（含司法解释）、**5 城**、**50 条**评测案例、**20 条**反例。

---

## 6. 测试与评测（这是项目的第二张脸）

### 6.1 跑什么

```powershell
python run_tests.py                       # 364 passed（零安装）
python -m pytest -q --cov=arb             # 带覆盖率（需 .libs 里有 pytest-cov）
$env:PYTHONPATH="src"; python -m scripts.eval_report    # → docs/eval_report.md
$env:PYTHONPATH="src"; python -m scripts.ablation       # → docs/ablation.md
```

### 6.2 各测试文件守什么

| 文件 | 守的东西 |
|---|---|
| `test_calc / test_severance / test_tenure / test_total / test_overtime / test_annualleave / test_nocontract` | 每个金额口径 |
| `test_deadline` | 时效起算与剩余天数 |
| `test_citations / test_laws` | 法条引用可核验、假法条能拦 |
| `test_scope / test_gap / test_web` | 拒答、追问、四种页面状态、XSS 转义 |
| `test_city_gates` | 五城口径、单字别名不误报、五类资格情形 |
| `test_worth_venue_materials` | 六维权重和为 1、金额维度单调、材料清单去重、路径不借用别城地址 |
| `test_confirm` | 未确认读数不进计算、冲突不择一 |
| `test_console / test_make_zip` | 零安装、编码、打包路径 |
| `test_schema / test_docs` | schema 合法、README 链接不 404 |
| `test_pdf / test_application / test_chips / test_mock_hr / test_evidence` | 输出与文案 |

### 6.3 加测试的三条规矩

1. **写测试要在解释为什么**：本项目每个测试文件顶部都有"为什么测这个"，出题人问的是判断力。
2. **不要给子进程传 pytest 插件参数**：`vendor/pkgs` 里**没有** pytest-cov，传 `--no-cov` 会让
   pytest 以退出码 4 结束。这是真踩过的坑（见 §7）。
3. **生成物必须可复现**：`scripts/eval_report.py`、`scripts/ablation.py` 生成文档时**不许写
   `date.today()`**，否则每次生成都产生 diff，CI 的 `git diff --exit-code docs/` 永远红。

### 6.4 当前水位（可作为"不许退化"的基线）

| 指标 | 值 |
|---|---|
| 单测 / 覆盖率 | 364 / 92% |
| 要素抽取 | 100%（222/222） |
| 试算金额命中 | 50/50 |
| 法条引用核验 | 84/84 |
| 资格闸门探针 | 5/5（误拦 0/50） |
| 城市口径探针 | 2/2 |
| 输出完整性 | 50/50；值得性理由引用 150/150 |
| 危险建议 | 0 |
| 消融 | A 5/50 → D 30/50；探针 D 8/8、E（去掉闸门）7/8 |

---

## 7. 真实踩过的坑（照这个清单避雷）

| # | 坑 | 症状 | 已加的防线 |
|---|---|---|---|
| 1 | **模块写完但没接进流水线** | `gates.py` 覆盖率 0%，`social_avg_wage` 永远是 null，3 倍封顶从未生效。单测全绿也发现不了 | 评测里加了"输出完整性"一节，直接看流水线吐出来的东西 |
| 2 | `schema.json` 是**非法 JSON** | `"social_avg_wage", "has_written_contract": {...}` 两个 key 挤一起；因为从没代码解析它，活了很久 | `tests/test_schema.py` 真的去 `json.load` 并核对字段 |
| 3 | **零安装测试传了 `--no-cov`** | 只有装了 pytest-cov 的机器才是绿的，而它名字叫"零安装" | 子进程参数修正 + 临时改名 `.libs` 实测 |
| 4 | **zip 包内路径用 `os.sep`** | Windows 生成 `a\b`，macOS/Linux 解压变成一个怪文件名而不是目录 | `make_zip._arc()` 统一正斜杠 |
| 5 | **写死默认城市** | `schema.json` 里 `default: "深圳"` 会让人以为全国按深圳算 | 去掉默认值，改 `examples` 五城 |
| 6 | **免责句被红线检查判违规** | 输出里写"这不是胜诉率"会被 `check_red_lines` 判成预测胜诉率 | `scope._negated()` 回看 8 字且按标点断句，否定语不计 |
| 7 | **`sfjs1:6` 引错条** | 一事不再理原本引解释（一）第 6 条（那是"不予受理后怎么诉"） | 改为不引条号并注明出处是《办案规则》（本库未收） |
| 8 | **`date.today()` 进生成物** | 每次重新生成都产生 diff，CI 无法检查文档一致性 | 生成物改固定口径日 |

---

## 8. 还没做的事（按"为什么没做"分类，不是按工作量）

### A. 卡在"需要真人"（AI 做不了，必须你们组做）

| # | 事项 | 现状 | 卡点 |
|---|---|---|---|
| A1 | 5 位真实劳动者前测后测 | 0 位 | 需要找到愿意试的劳动者 |
| A2 | 5 位非技术同学盲读报告（读几分钟、卡在哪句） | 0 份 | 随时可做，只差约人 |
| A3 | 危险建议两人独立人工复核 | 自动扫描 0 条，人工 0 份 | 需要两个独立标注的人 |
| A4 | G1 单人复核：另一人用 5 个真实案例手算对照 | 未做 | 需要第二个人 |
| A5 | 彩排 3 次（全程掐表、断网演练 1 次） | 0 次 | 需要三人到场 |
| A6 | 5 分钟演示视频 | 未录 | 需要录屏环境，先定"是否入镜真人" |

> A1–A5 是 **G5 门禁关不上**的原因。G5 定义是"全部达标才允许交付"，所以它现在是**阻塞**状态，
> 不是"待办"。

### B. 卡在凭据 / 无 key

| # | 事项 | 说明 |
|---|---|---|
| B1 | ~~push 到 GitHub~~ | **已完成**：远端 `cfe31b7`，本地一致（`git ls-remote origin refs/heads/main` 可验） |
| B2 | 真实 LLM 抽取效果 | 无 key。"纯大模型直答"那一臂在消融表里**留空**，不是 0 分；`scripts/llm_baseline.py` 就绪但没跑过 |
| B3 | LoRA 微调 | 明确放弃：无 GPU / 无 key，且规则抽取已 100%。理由已留档 |

### C. 功能缺口（对比过同类项目 `awaw49/labor-aid`，仍未做）

| # | 缺口 | 影响 | 建议 |
|---|---|---|---|
| C1 | **类案参考库**（争议焦点/要旨/可比点/不可比点） | 报告里只能引法条，不能引类案；对方项目有 13 份 | **优先级最高**。注意：`data/cases.jsonl` 是评测集，**不是**类案库，两者不可混用；新增必须用公开典型案例并保留来源，不许编造案号 |
| C2 | 语音转写 / 拍照 OCR / 图片读数 | 只有字段层确认链，没有图片入口 | **建议不做**。装 faster-whisper / Vision OCR 会直接毁掉"零安装、无依赖"这个最大优势 |
| C3 | PWA / 离线缓存 | 无 manifest、无 service worker | 低优先。单页已经能在断网下用（数据都在本地） |
| C4 | 会话状态 | 全仓库 `session`/`cookie` 命中 0；同一问题可能被重复追问，关页即丢 | 中优先。加最小会话（内存 dict + cookie）即可，注意不要引入持久化隐私风险 |
| C5 | `SECURITY.md` / `CONTRIBUTING.md` / `CHANGELOG.md` | 只有 LICENSE 和 CI | 低优先。若要公网部署，必须补"加认证+限流+HTTPS"的说明 |
| C6 | 关注度较低的案件类型 | `在编`/`公务员`/`事业单位`/`非全日制` 关键词命中 **0** ——既不计算也不拦截 | 中优先。至少要在 `scope.py` 里加"指路"，不许静默算出金额 |

### D. 数据时效风险

| # | 风险 | 现状 |
|---|---|---|
| D1 | 五城口径会过期 | 核验日 `2026-11-04`；有 `verified_at` 字段，但**没有到期提醒/复核流程** |
| D2 | 一裁终局线口径 | 统一按"最低工资×12"，各地细则可能有差异，只做了一句标注 |
| D3 | 法条库是快照 | 519 条已固化；`scripts/fetch_laws.py` 需联网，无增量更新/版本比对 |
| D4 | 跨城市社平不可比 | 深圳用"城镇非私营在岗职工"口径，部分城市用"全口径"，已注明但未归一化 |

### E. 方法论局限（文档里写了，没解决）

| # | 局限 |
|---|---|
| E1 | 值得性六维权重（25/25/10/15/10/15）是**人为设定**，不是从真实案件分布回归出来的 |
| E2 | 二倍工资尾数默认"不足一月不计"，与司法解释（二）第 6 条"按该月实际工作日折算"不完全一致（可切换，默认保守） |
| E3 | 引用校验第一层有 1 条语义盲区（`neg-12`：原文词都在、关系被反写），需要第二层语义核对，而那层没接 |
| E4 | 范围/闸门判定基于正则，只覆盖高频说法，长尾会漏 |

### F. 文档债（已完成但没勾，可直接补）

`docs/执行计划与验收清单.md` 里有 8 处 `- [ ]` 其实已完成：`S0.2 仓库骨架`、G1 的三条
（≥40 条全绿 / 覆盖率 ≥90% / 反例库）、`S2.3 案例库 50 条`、G2 的三条。
另外 `logs/G1_gate.md` **不存在**，而验收要求"结论写入 `logs/G1_gate.md`"。

---

## 9. 明确不要做的事

| 不要 | 为什么 |
|---|---|
| 引入第三方运行时依赖（Flask / FastAPI / numpy / pydantic…） | "clone 下来一条命令能跑"是最大的交付优势；CI 有一个 job 专门在"什么都没装"的环境跑测试 |
| 让模型算金额，或让模型直接写结论 | 违反 §4.1、§4.2；`184,137.93` 等数字会变得不可复现 |
| 给未覆盖的城市编社平工资 | 违反 §4.5；宁可说"没覆盖"，不许拿别的城市数字顶 |
| 改 `demo.py` 的 `DEMO_TODAY` 或演示口径 | `184,137.93` 同时出现在 3 个测试和 2 份文档里，改了会连环红 |
| 改 `Policy` 默认值而不改测试 | `tests/test_nocontract.py` 有"不足一月"的三口径断言 |
| 在生成物里写 `date.today()` | 破坏 CI 的"文档与代码一致"检查 |
| 把 `data/cases.jsonl` 当类案库用 | 它是评测集，每条带金标准；混用会让评测失真 |
| 用 `pip install` 修 CI | 先确认零安装路径没坏（`vendor/pkgs` 够用） |

---

## 10. 接手后前 30 分钟（照做）

```powershell
cd arbitration_assistant

# 1) 确认基线（约 4 秒）
python run_tests.py
#    期望：364 passed

# 2) 确认远端一致
git status -sb                      # 应为 "## main"，无 ahead/behind
git ls-remote origin refs/heads/main # 应等于 git rev-parse main

# 3) 确认端到端能出结果
python -m arb.cli "2020年3月1日入职，月薪9000，一直没签书面合同。2024年5月20日主管口头说不要我了，还有5天年假没休。"
#    期望：合计 184,137.93 元；3 个金额项；5 条法条引用，行末都是 ✅（不是 ⚠️）

# 4) 确认评测/消融可复现（不产生 diff）
$env:PYTHONPATH="src"
python -m scripts.eval_report; python -m scripts.ablation
git status --short docs              # 应为空

# 5) 起网页看一眼
python run.py                        # 浏览器打开 127.0.0.1:8765
```

五步全过，说明你拿到的是完整可用的版本。任何一步不符，先别改代码——先查环境。

---

## 11. 建议的下一步（如果要继续做）

按性价比排序，前两条都不需要新数据源：

1. **补 `logs/G1_gate.md` + 勾掉 8 处 stale checkbox**（§8F）—— 半小时，纯文档债，
   能让验收清单与代码一致，评审最容易发现的不一致就在这里。
2. **C4 最小会话状态**：把"已经问过什么、问了几次"记住，避免同一问题重复追问。
   只加内存态 + cookie，不落盘。
3. **C6 四类案件指路**：在 `scope.py` 里给"在编/公务员/事业单位/非全日制"加拒答+指路，
   绝不能让它们静默算出金额。
4. **C1 类案库**：工作量最大、收益也最大（报告从"只引法条"升级到"法条+类案"）。
   必须用公开典型案例、保留来源、不许编案号。
5. **D1 口径到期提醒**：`verified_at` 超过 12 个月就在报告里提示"数据可能过期，请重新核验"。

---

## 12. 认词表（避免沟通错位）

| 词 | 在本项目里的确切含义 |
|---|---|
| N / 2N | 经济补偿 / 违法解除赔偿金（2N 已含 N，不叠加） |
| 二倍工资 | 未签书面合同的**另一倍**工资，最多 11 个月，不是把已发工资再算一遍 |
| 一裁终局 | 标的额 ≤ 当地最低工资×12 时，裁决作出即生效，单位不能起诉只能申请撤销 |
| 3 倍封顶 | 月工资 > 当地社平×3 时，按 3 倍算且年限 ≤12 年（劳动合同法 47） |
| 硬障碍 / blocked | 一事不再理等"门都进不去"的情形，此时**不给金额** |
| warn | 有风险但仍可申请（跨城市、退休返聘、时效紧张…），给金额但把提醒放最前 |
| pending | 来自模型/图片、尚未经用户确认的读数，**不参与计算** |
| 值得性 | 六维加权分，用于排"先做什么"，**不是胜诉率** |
| 覆盖城市 | 京/沪/广/深/杭五城，各有独立口径 JSON；其它城市明说"未覆盖" |

---

## 13. 联系人 / 责任边界

- 代码与文档：本仓库；远端 <https://github.com/chinesecanfly99/arbitration-assistant>
- 交付包：`python -m scripts.make_zip` → 仓库**上一级**目录的 `劳动仲裁维权助手_交付包.zip`
- 法律边界：本项目**不提供法律意见**，不预测胜诉率，不教人造假证据；工伤/社保补缴/公积金只指路不结论；
  兜底引导 **12348** 法律援助
