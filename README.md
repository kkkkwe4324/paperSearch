# Paper Downloader

完整使用方法见 [USAGE.md](USAGE.md)。

跨研究文件夹复用的目录、论文 MD 清单和 Zotero 分类流程见 [LLM_WORKFLOW.md](LLM_WORKFLOW.md) 与 [示例工作区](examples/research-workspace/README.md)。

给自动化助手的固定操作流程见 [LLM_QUICKSTART.md](LLM_QUICKSTART.md)。

命令行批量下载有权访问的 IEEE Xplore 和 ACM Digital Library PDF。首次手动完成一次南科大 SSO/CARSI 登录，之后复用本地浏览器 profile 下载多篇论文。

## 安装

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 首次登录

```powershell
python -m paper_downloader login
```

浏览器打开后，手动完成南科大机构认证、验证码和 MFA，回到终端按 Enter。程序不会接收或打印密码。

## 批量下载

创建 `papers.txt`，每行一个 DOI；空行和 `#` 开头的行会被忽略：

```text
# IEEE
10.1109/example.1234567
# ACM
10.1145/1234567.1234568
```

执行：

```powershell
python -m paper_downloader download papers.txt --output downloads `
  --cdp --cdp-port 9222 --min-delay 15 --max-delay 30 --resume
```

`10.1109/` 路由到 IEEE，`10.1145/` 路由到 ACM。登录后下载也使用同一个 CDP Chrome（加上 `--cdp`），默认每篇随机间隔 15–30 秒，遇到认证失效或限流会立即停止并保存状态；有效 PDF 会在 `--resume` 下跳过。状态写入 `downloads/download-state.jsonl`。

如果机构会话过期或服务限流，程序会停止批处理并报告 `auth_required` 或 `rate_limited`；完成登录或等待后再运行同一命令即可。

请只下载本人通过南科大订阅合法访问的内容，并遵守学校和出版商的使用条款。

## Google Scholar 检索

安装依赖后可按关键词检索论文：

```powershell
python -m pip install -r requirements.txt
python -m paper_downloader search "microgrid energy management" --pages 5
```

每页默认 10 条，页间随机等待 20–40 秒，单次最多 5 页。结果会在终端分页显示，并保存到 `results/` 下的 JSONL 和 CSV 文件，包含标题、作者、会议/期刊、年份、摘要片段、引用数和 DOI。重复查询会直接使用本地缓存；需要重新访问时加 `--refresh`。已获取结果会保留在本地，便于按摘要初筛；其中的 IEEE/ACM DOI 可以复制到 `papers.txt` 再交给下载命令。

Google Scholar 若返回 CAPTCHA、429 或机器人验证，程序会停止本次查询，不使用代理轮换或 CAPTCHA 绕过。Scholar 不保证每条记录都有完整摘要，缺失时会显示结果片段。

如果 Playwright 模式反复触发验证，推荐使用真实 Chrome 的 CDP 模式。先关闭使用中的 Chrome 窗口，再用固定 profile 启动一个专用 Chrome：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:USERPROFILE\.paper-downloader\scholar-chrome-profile" `
  --no-first-run --no-default-browser-check about:blank
```

在该 Chrome 中手动打开 Scholar、完成登录和验证，然后执行：

```powershell
python -m paper_downloader search "PINN power system" --pages 3 --cdp
```

程序会连接这个已打开的 Chrome，单页串行搜索并在验证页面自动等待。不要删除 profile，也不要同时启动多个搜索进程；遇到验证时只在 Chrome 中手动处理，不要反复刷新。
