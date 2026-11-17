# Render 免费云端部署

部署目标：从 `chinesecanfly99/arbitration-assistant` 的 `main` 分支创建 Render 新加坡免费 Web Service，获得电脑和手机均可访问的 HTTPS 网址。

> 原 Zeabur 方案已经过时。Zeabur 官方公告：部分服务从 2026-12-01 起停止，全部独立服务器和共享集群在 2026-12-31 前关闭。参见 [官方公告](https://zeabur.com/zh-CN/blogs/zeabur-is-shutting-down)。

## 免费方案与节点

- 使用 `Free` 实例，不创建付费实例、数据库或磁盘。
- Render 没有香港节点；本方案使用新加坡 `singapore`。
- 连续 15 分钟无访问后会休眠，再次访问通常需要约一分钟启动。
- 免费实例时长为每个工作区每月 750 小时，多个免费服务共享额度。带宽和构建也有额度限制。没有支付方式时，额度耗尽会暂停相关服务或构建。
- HTTPS 网址由 Render 提供，实际域名以控制台显示为准。
- 免费的是云端托管额度；DeepSeek API 仍按 DeepSeek 的计费规则扣费。
- 免费服务适合课程演示和个人试用，不能保证全天即时响应或长期不变的免费政策。

官方资料：[免费部署](https://render.com/docs/free)、[节点](https://render.com/docs/regions)。

## 方式一：使用仓库内 Blueprint

1. 在 [Render 控制台](https://dashboard.render.com/) 登录；首次注册、账号授权和服务条款由账号持有人确认。
2. 选择 **New → Blueprint**，关联 `chinesecanfly99/arbitration-assistant`，分支选择 `main`。
3. Render 读取根目录的 `render.yaml`，核对：

   | 配置 | 值 |
   | --- | --- |
   | Name | `arbitration-assistant` |
   | Runtime | Python |
   | Region | Singapore |
   | Plan | Free |
   | Build Command | `python run_tests.py` |
   | Start Command | `python -u run.py` |
   | Health Check Path | `/` |

4. 在 `ARB_LLM_API_KEY` 的输入框中填写自己的 DeepSeek Key。`sync: false` 只声明变量名，仓库中不保存密钥值。
5. 创建服务并等待构建通过、状态变为 **Live**。记录控制台显示的 `https://….onrender.com` 网址。

## 方式二：手动创建 Web Service

如果当前账号无法使用 Blueprint，选择 **New → Web Service**，连接同一仓库及 `main` 分支，手动填写上述配置。也可以通过 Public Git Repository 输入仓库地址进行部署；这种方式的自动更新能力以控制台说明为准。

环境变量：

| 变量 | 值 |
| --- | --- |
| `PYTHONIOENCODING` | `utf-8` |
| `PYTHONUNBUFFERED` | `1` |
| `ARB_LLM_BASE_URL` | `https://api.deepseek.com/v1` |
| `ARB_LLM_MODEL` | `deepseek-chat` |
| `ARB_LLM_API_KEY` | 只在 Render 环境变量中填写真实值 |

`.python-version` 选择 Python 3.12 的最新可用补丁版本。运行时只依赖标准库，构建阶段使用仓库内的测试依赖执行测试。Render 自动提供 `PORT`，`run.py` 据此监听 `0.0.0.0:$PORT`，无需手动固定端口。

## 密钥与使用范围

- 不要将 `.env`、真实 API Key、控制台变量截图提交到 GitHub。
- 不配置 API Key 也能运行规则计算与离线演示；实时 AI 对比需要有效 Key。
- 使用服务器 Key 时，请求参数不能改写它的接口地址和模型；访客需要使用其他接口时必须提供自己的 Key。
- 公开网址的访问者能够触发服务端的模型调用。Key 不会展示到页面，但 API 费用仍由 Key 的持有人承担；上线前请核对 DeepSeek 余额与用量控制。

## 上线验收

- 首页返回 HTTP 200，默认英文，右上角可切换中文。
- 演示案例可计算，四个板块可切换。
- 配置有效 Key 后，实时 AI 对比可得到结果；API 余额不足、超时或访问受限时检查 Render 日志。
- PDF 与仲裁申请书草稿可以下载。
- 在手机上访问同一 HTTPS 网址，检查布局与交互。
- 语音输入还依赖浏览器支持、设备麦克风和用户授权，需要在实际设备上验证。

## 更新与排障

- 正常关联 GitHub 且开启自动部署时，推送 `main` 会触发重新部署。
- 仅连接 Public Git Repository 时，可能需要手动触发部署最新提交。
- 构建失败先查看测试输出，不要跳过失败的测试后强行上线。
- 返回 502 时确认启动命令为 `python -u run.py`，日志包含 `0.0.0.0` 及 Render 分配的端口。
- 改动 API Key 后保存环境变量并重新部署，密钥始终不进 Git。
