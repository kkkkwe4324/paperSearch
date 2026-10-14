# 给另一个 LLM 的快速配置协议

## 目标

使用同一个本地 Chrome 会话完成 Scholar 检索和 IEEE/ACM/ScienceDirect 授权下载。只下载用户明确选择、且账号有权访问的论文。

## 一次性准备

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m paper_downloader login --cdp-port 9222
```

登录命令打开的 Chrome 中，用户手动完成 IEEE/ACM 南科大 SSO、验证码和 MFA。LLM 不得输入密码、验证码或 MFA。

## Scholar 检索

```powershell
python -m paper_downloader search "完整研究主题关键词" `
  --pages 1 --page-size 10 --cdp --cdp-port 9222 --refresh
```

默认每页等待 20–40 秒，单次最多 5 页。优先读取生成的 `results/*.jsonl` 和 `results/*.csv`。Scholar 没有 DOI 时，LLM 必须让用户确认 DOI，不能猜测。

## 下载

把用户确认过的 DOI 写入 `papers.txt`，然后始终复用同一个 CDP Chrome：

```powershell
python -m paper_downloader download papers.txt `
  --output downloads --cdp --cdp-port 9222 `
  --min-delay 15 --max-delay 30 --retry-count 3 --resume
```

每次运行后检查：

1. 退出码为 `0`；
2. `downloads/download-state.jsonl` 对应记录为 `success`；
3. PDF 文件存在且不是 HTML 错误页。

## 必须停止的情况

- 出现 CAPTCHA、AWS WAF、429、403 或 `rate_limited`：立即停止，不刷新、不换代理、不重试刷请求。
- 出现 `auth_required`、`denied` 或登录页：让用户在同一个 Chrome 中完成认证，再重新运行 `--resume`。
- 下载结果不是 PDF：不要把响应保存为论文，保留状态文件并报告原因。

## 不得做的事

- 不启动多个搜索或下载进程。
- 不使用小于 20 秒的 Scholar 间隔或小于 15 秒的下载间隔。
- 不读取、打印、上传 Cookie、浏览器 profile、密码或 MFA。
- 不绕过验证码、机构授权或出版商访问限制。
