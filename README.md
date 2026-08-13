# 微信公众号每日新闻早报

每天北京时间 08:30 通过微信推送当日早报，新闻按 **科技 / 财经 / 国际 / 国内·社会** 四个类别划分。

## 效果预览

每天收到 **4 条消息**（每类一条，客服消息单条限 600 字符）：

```
【科技】8月13日早报
1. 英特尔 CEO 陈立武暗示将重返内存市场（IT之家）
   https://www.ithome.com/0/989/147.htm
2. ...
【财经】8月13日早报
1. 联想集团第一财季营收269.4亿美元（东方财富）
   ...
```

早报模式：8:30 推送时覆盖**昨日 00:00（北京时间）至今晨**的新闻，信息完整。

### ⚠️ 48 小时互动窗口（重要）

客服消息要求**用户在 48 小时内与公众号互动过**（发消息即激活）。收到早报后**回复任意一条消息**（如"早"），窗口即自动续期 48 小时。忘回超过 48 小时会推送失败（Actions 日志可见 errcode 45015），此时发一条消息后次日恢复。

## 架构

```
GitHub Actions (cron UTC 00:30 = 北京 08:30)
  → src/main.py
     → sources.py   抓取 4 类别新闻（IT之家/少数派 RSS、东方财富快讯 API、中新网 RSS、百度热搜）
     → formatter.py 早报过滤（昨日 00:00 起）、去重、主源优先、排版 ≤2048 字节
     → wechat.py    access_token + 客服消息推送（模板消息兜底）
```

## 快速开始

### 1. 申请微信测试号（5 分钟，零成本）

微信测试号是官方开发者沙盒，**无需注册/认证公众号**：

1. 浏览器打开 <https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login>
   （注意：经典地址 `sandbox` 不带参数已失效，会返回 `{"errcode":0,"errmsg":"ok"}` JSON）
2. 微信扫码确认登录，页面显示 **appID** 和 **appsecret**，记下备用
3. 页面下方"测试号二维码"：用**自己的微信扫码关注**
4. 关注后刷新页面，在"关注者列表"中查看自己的 **openid**

### 2. 本地运行（可选）

```bash
pip install -r requirements.txt
cp .env.example .env    # 填入 appID / appsecret / openid
python src/main.py      # 微信应立即收到早报
```

### 3. 部署到 GitHub Actions

1. 把本目录推到 GitHub 仓库
2. 仓库 **Settings → Secrets and variables → Actions** 添加：
   | Secret | 值 |
   |--------|-----|
   | `WECHAT_APP_ID` | 测试号 appID |
   | `WECHAT_APP_SECRET` | 测试号 appsecret |
   | `WECHAT_OPENIDS` | 接收者 openid（多个用逗号分隔） |
3. **Actions → daily-news → Run workflow** 手动触发一次验证
4. 确认收到后，每天 08:30 自动推送（GitHub 免费版 cron 可能有分钟级延迟，属正常）

### 可选配置

- `NEWS_PER_CATEGORY`：每类新闻条数（默认 4，单条消息 600 字符内）
- `WECHAT_TEMPLATE_ID`：客服消息失败时的模板消息兜底通道（需在测试号"模板消息"页添加模板后填 ID）

## 新闻源

| 类别 | 主源 | 备选 |
|------|------|------|
| 科技 | IT之家 RSS | 少数派 RSS |
| 财经 | 东方财富 7x24 快讯（公开 API） | — |
| 国际 | 中新网 RSS | 环球网 via RSSHub |
| 国内/社会 | 百度热搜 | 澎湃 via RSSHub |

- 主源条目优先展示，备选源（全站内容、类别不纯）只在主源条数不足时补位
- 源失效排查：`python scripts/probe_sources.py` 逐源探测，失效源在 `src/sources.py` 中替换

## 目录结构

```
├── .github/workflows/daily-news.yml  # 每日 08:30 定时 + 手动触发
├── src/
│   ├── main.py       # 入口：抓取 → 过滤 → 排版 → 推送
│   ├── config.py     # 环境变量读取、类别配置
│   ├── sources.py    # 各新闻源抓取
│   ├── formatter.py  # 早报过滤、去重、主源优先、排版
│   └── wechat.py     # 微信 API：token + 客服消息（模板消息兜底）
├── scripts/probe_sources.py  # 新闻源连通性探测
├── requirements.txt
└── .env.example
```
