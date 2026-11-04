# Day6 日志：把「能演示」补成「能录、能彩排、能被非技术读者看懂」

> 目标：S6.3（演示视频）与 S6.5（彩排）的**准备工作**做到底，同时不假装视频和真人测试已经完成。
> 原则：演示与评测用同一套代码；演示脚本里出现的每个数字，都要能一条命令复现。

## 一、目标 → 实测 → 证据

| # | 目标 | 实测 | 证据 |
| --- | --- | --- | --- |
| 1 | 一个命令跑完三屏演示 | ✅ `python -m arb.demo`：能算清的（184,137.93 元 / 3 项 / 4 条法条）→ 说不清的（追问 2 个问题、不给钱）→ 不该它管的（工伤指路、胜率拒答） | `src/arb/demo.py`、`tests/test_demo.py`（6 条） |
| 2 | 演示必须可复现（不能每次数字不一样） | ✅ 演示口径固定 `DEMO_TODAY = 2024-06-01`，时效"还剩 353 天"每次一致；真实使用不传 today | `tests/test_demo.py::test_scene_full_is_deterministic` |
| 3 | 演示要证明"边界"，不能只炫功能 | ✅ 第 2、3 屏分别证明"该问就问"和"不归它管就不接" | `src/arb/demo.py:scene_gap/scene_out` |
| 4 | 给录视频的人一份逐句脚本 | ✅ `docs/demo_script.md`：0:00–5:00 分镜、台词、只演 4 样、断网预案、4 条翻车点 | 文档 + `tests/test_docs.py` 校验时间轴 |
| 5 | 给非技术读者一页纸 | ✅ `docs/one_pager.md`：它有多准 / 什么时候故意不做事 / 拆件测试 / 还差什么 | 文档 |
| 6 | 给答辩一份彩排稿 | ✅ `docs/rehearsal.md`：3 遍演练的分工与通过标准、8 个必被问的问题（套壳/幻觉/为什么不做全国/真人测试…）、4 条"不要说的话"、故障演练表 | 文档 + `tests/test_docs.py` 校验关键问题 |
| 7 | README 第一屏能路由 | ✅ 加"你是谁 → 先读哪份"表：评委/录视频/彩排/复现 | `README.md` 快速开始节 |
| 8 | 文档不能断链、不能占位 | ✅ `tests/test_docs.py` 4 条（链接存在、文档>500 字、脚本含时间轴与断网预案、彩排含 4 个关键问题） | 测试通过 |
| 9 | 报告能下载成 PDF（用户要发给家人/拿去仲裁委） | ✅ 纯标准库手写 PDF：9,434 字节、文本层可解码、合计 184,137.93 元；网页 `/pdf` 路由 + 报告页"⬇ 下载 PDF"按钮 | `src/arb/pdf.py`、`tests/test_pdf.py`（8 条）、`docs/sample_report.pdf` |
| 10 | 全量回归 | ✅ **282 passed / 覆盖率 92%** | `PYTHONPATH=.libs python -m pytest -q --cov=arb` |

## 二、演示脚本反而抓出两个抽取缺口（真收获）

写 `SCENE_FULL` 时用了更口语的说法，跑出来是 `need_more`，于是暴露两处：

1. **"一个月9000"抽不到月薪**：`WAGE` 只认「月薪/月工资/工资」。补 `一个?月|每月`，并允许「给/拿/挣」等口语动词。
   → 回归测试 `test_colloquial_monthly_wage`。
2. **"一直没跟我签书面合同"判成"未提及"**：否定式只写了「一直没给我签」，漏了「没跟我签」。
   → 补 `一直没(?:跟|给|和)我?签|没跟我签`，回归测试 `test_colloquial_no_contract`。

教训：**评测集是作者写的故事，会不自觉地用"系统能懂的说法"**。演示脚本要求"像真人说话"，反而成了抽取层的对抗测试。
（这也解释了为什么金额从 85,137.93 变回 184,137.93 —— 差的就是那 99,000 的二倍工资。）

## 三、修完复测

| 检查 | 结果 |
| --- | --- |
| 字段抽取 | 100%（222/222，五字段全 50/50） |
| 金额命中 | 50/50 |
| 引用核验 | 84/84 |
| 消融四臂 | A 5/50 · B 5/50 · C 30/50 · D 30/50（未变） |
| 单测 | 282 passed / 92% |

## 三·补、PDF 为什么是手写的

想走"网页打印成 PDF"的老路，先试 Edge 无头模式：

1. `subprocess.run(["msedge", "--headless", "--print-to-pdf", ...])` → `PermissionError: [WinError 5]`（CreatePipe 被拒）。
2. 改成把 stdout/stderr 重定向到日志文件再读 → Chromium 自己崩：`crashpad_client_win.cc(426)] OpenProcess: 拒绝访问` + `platform_channel.cc(152)] FATAL`。

沙箱不允许拉起 Chromium 的 IPC，说明这条路在这台机器上不可能稳。于是自己写 PDF：

- A4 595×842、页边距 50，`STSong-Light` + `UniGB-UCS2-H`（PDF 标准中文字体，**不嵌字体**，阅读器用系统宋体替换）。
- 文本全部写成 `<UCS2 十六进制> Tj`，所以 PDF 里的中文**可复制、可搜索**，不是图片。
- xref 偏移逐条自检，`validate()` 能抓出坏文件（测试里专门喂了一个坏 PDF）。

两个真坑：
1. `_send()` 原来直接 `body.encode("utf-8")`，发 bytes 时抛异常、HTTP 连接直接断（表现是 `RemoteDisconnected`，而不是 500）。改成 `body if isinstance(body, bytes) else body.encode()`。
2. 我自己第一版 `validate()` 用 `text.rsplit("\\nxref\\n")` —— 源文件写入时被转义成字面反斜杠，永远匹配不到，自检**假通过**。改成 `chr(10)` 拼接后立刻抓出三条偏移错误。

## 三·补二、还欠什么（不假装做完）

| 事项 | 状态 | 卡在哪 |
| --- | --- | --- |
| S6.3 5 分钟视频 | 脚本 + 一键演示就绪，**未录** | 需录屏环境；且要先定"是否入镜真人" |
| S6.5 彩排 3 次 | 彩排稿就绪，**未彩排** | 需三人到场同时掐表 |
| 真人前测后测（G5 人工半边） | **未做** | 需 5 位真实劳动者 + 1 位 HR/律师 |
| 深圳社平工资口径 | 仍为 `null` | 需用户确认写死哪一年 |
| "纯大模型直答"对照臂 | 脚本就绪、未运行 | 本机无模型 key，不编结果 |

## 五、复现命令

```bash
cd F:\DSH_file\arbitration_assistant
PYTHONPATH=src python -m arb.demo                    # 三屏演示（录视频/现场用）
PYTHONPATH=src python -m arb.web                     # 网页版 http://127.0.0.1:8765
PYTHONPATH=src python -m arb.pdf -o docs/sample_report.pdf   # 导 PDF（自检不过返回 1）
PYTHONPATH=.libs python -m pytest -q --cov=arb       # 282 passed / 92%
PYTHONPATH=src python -m scripts.eval_report         # 重生成 docs/eval_report.md
PYTHONPATH=src python -m scripts.ablation            # 重生成 docs/ablation.md
```
