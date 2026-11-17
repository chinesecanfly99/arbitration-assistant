# Zeabur 部署方案已停用

2026-11-17 核查：Zeabur 官方已宣布，部分服务从 **2026-12-01** 起陆续停止，全部独立服务器和共享集群在 **2026-12-31** 前关闭。

来源：[Zeabur 停止运营公告及服务迁移安排](https://zeabur.com/zh-CN/blogs/zeabur-is-shutting-down)。

因此不再按原指南新建 Zeabur 服务，也不向 Zeabur 上传新的 API Key。

本项目改用 **Render 新加坡免费 Web Service**，配置保存在根目录 [`render.yaml`](../render.yaml)。完整部署与验收步骤见 [`render_deploy.md`](render_deploy.md)。

Render 无香港节点；用户已确认改用新加坡。免费实例闲置后会休眠，不能保证全天即时响应。DeepSeek API 费用与免费托管分开计算，真实 Key 只在 Render 环境变量中填写，不进入代码、文档或 Git。
