# Paper Downloader 使用说明

面向第一次使用本工具的人或 LLM。完整流程是：

```text
关键词检索 → 摘要初筛 → 选择 DOI → 批量下载 PDF → 阅读 Introduction
```

## 安装

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Scholar 检索

推荐使用可见浏览器模式：

```powershell
python -m paper_downloader search "physics-informed neural network" --pages 3 --browser
```

常用参数：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `query` | 必需 | 搜索关键词 |
| `--pages` | `3` | 最大页数（最多 5 页） |
| `--page-size` | `10` | 每页结果数 |
| `--browser` | 关闭 | 使用持久化浏览器，推荐开启 |
| `--refresh` | 关闭 | 忽略缓存、重新搜索 |
| `--results-dir` | `results` | 结果目录 |
| `--data-dir` | `~/.paper-downloader` | 浏览器 profile 目录 |

每条结果包含：标题、作者、会议/期刊、年份、摘要片段、引用数、DOI（能识别时）和 IEEE/ACM 类型。

结果保存为：

```text
results/<query-hash>.jsonl
results/<query-hash>.csv
```

重复执行相同查询会优先读取缓存；只有需要重新访问 Scholar 时才使用 `--refresh`。

如果终端提示人工验证，请在弹出的浏览器中完成验证，然后回到终端按 Enter。程序不会破解 CAPTCHA、轮换代理或绕过访问限制。

### 推荐：连接真实 Chrome 搜索 Scholar

如果上面的 Playwright 浏览器反复触发验证，先关闭正在使用的 Chrome 窗口，再启动一个专用、固定 profile 的 Chrome：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:USERPROFILE\.paper-downloader\scholar-chrome-profile" `
  --no-first-run --no-default-browser-check about:blank
```

在弹出的 Chrome 中手动打开 `https://scholar.google.com`，完成 Google 登录和人工验证后，执行：

```powershell
python -m paper_downloader search "PINN power system" --pages 3 --cdp
```

`--cdp-port` 默认是 `9222`，端口不同则显式指定，例如 `--cdp-port 9333`。CDP 模式只连接已有 Chrome，不会在搜索结束时关闭它；搜索按页串行执行，页间默认等待 20–40 秒。不要同时运行多个搜索进程，也不要删除 profile。

短关键词容易产生无关结果。例如 `PINN` 可能匹配作者 `Pinn`。推荐使用：

```powershell
python -m paper_downloader search "physics-informed neural network microgrid" --pages 5 --browser
python -m paper_downloader search "PINN power system" --pages 5 --browser
```

## 选择 DOI

阅读 CSV/JSONL 后，把选中的 DOI 写入 `papers.txt`，每行一个：

```text
# IEEE
10.1109/EXAMPLE.1234567

# ACM
10.1145/1234567.1234568
```

也支持 `https://doi.org/...` 和 `doi:10...` 形式。空行、注释行和重复 DOI 会被忽略。

当前只支持：

- `10.1109/...` → IEEE Xplore；
- `10.1145/...` → ACM Digital Library。

其他 DOI 不会被猜测或强行下载。

## 一次登录，批量下载

首次登录：

```powershell
python -m paper_downloader login
```

在浏览器中手动完成南科大 SSO/CARSI、验证码和 MFA，完成后回到终端按 Enter。profile 默认位置：

```text
%USERPROFILE%\.paper-downloader\browser-profile
```

然后批量下载：

```powershell
python -m paper_downloader download papers.txt --output downloads `
  --cdp --cdp-port 9222 --min-delay 15 --max-delay 30 --resume
```

下载器会复用同一个浏览器会话，不需要每篇重新登录。它会逐篇路由、下载、校验 `%PDF-` 文件头，并把成功/失败状态写入：

```text
downloads/download-state.jsonl
```

常用下载参数：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `INPUT` | 必需 | DOI 文件 |
| `--output` | `downloads` | PDF 目录 |
| `--min-delay` / `--max-delay` | `15` / `30` | 每篇随机间隔范围（秒） |
| `--retry-count` | `3` | 单篇最大重试次数 |
| `--resume` | 关闭 | 跳过已有有效 PDF |

如果登录会话失效，程序会记录 `auth_required` 并停止。重新执行 `login` 后，再运行同一下载命令即可。

## 下载后的筛选

推荐阅读顺序：标题/摘要 → 结论 → Introduction → Method → Experiments。记录 DOI、文件名以及保留或排除原因。

## 文件与安全

| 路径 | 内容 |
|---|---|
| `results/*.jsonl` | Scholar 结果，适合 LLM/程序读取 |
| `results/*.csv` | Scholar 结果，适合人工筛选 |
| `downloads/*.pdf` | 成功下载的 PDF |
| `downloads/download-state.jsonl` | 下载状态 |
| `~/.paper-downloader/browser-profile` | 敏感登录状态 |

不要分享或提交 browser profile、Cookie、密码和下载日志。只下载本人通过南科大合法授权访问的内容。

## 常见问题

### Scholar 仍然 CAPTCHA

停止重复刷新，等待一段时间后再试；减少页数并使用更具体的关键词。程序不会绕过验证。

### 结果没有 DOI

Scholar 不保证页面显示 DOI。可从论文详情页、出版社页面、Crossref 或 DBLP 手动确认后加入 `papers.txt`。

### 下载显示无权限或不是 PDF

重新执行 `login`，确认 IEEE/ACM 页面显示机构授权。程序会拒绝保存登录 HTML、错误页或其他非 PDF 响应。

## 给 LLM 的操作规则

1. 优先使用完整关键词和 `--browser`。
2. 先按标题、会议/期刊、年份和摘要片段初筛。
3. 明确把摘要片段标记为 snippet，不冒充完整摘要。
4. 只把用户选中的 DOI 写入 `papers.txt`。
5. 下载使用 `--resume`，避免重复请求。
6. 遇到 CAPTCHA、429、登录页或未授权时停止并提示用户。
7. 不猜 DOI、不绕过认证、不分享 Cookie 或 browser profile。
