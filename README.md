# 📰 RSS 每日摘要 - GitHub Actions 版

零成本、免维护的 RSS 推送方案，使用 GitHub Actions 定时运行。

## 功能

- ✅ 每天早上 8:00 自动抓取 RSS
- ✅ 按分类整理（AI 资讯、科技资讯等）
- ✅ 推送到飞书（支持其他平台）
- ✅ 零服务器成本（GitHub 免费额度）

## 快速开始

### 1. Fork 本项目

点击右上角 **Fork** 按钮

### 2. 配置 RSS 源

编辑 `config/feeds.json`，添加你想订阅的源：

```json
{
  "feeds": [
    {
      "name": "量子位",
      "url": "https://www.qbitai.com/rss",
      "category": "AI 资讯"
    }
  ]
}
```

### 3. 配置飞书 Webhook

1. 在飞书群添加机器人 → 复制 Webhook 地址
2. 在 GitHub 仓库 → Settings → Secrets and variables → Actions
3. 新建 Secret：
   - Name: `FEISHU_WEBHOOK`
   - Value: `https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx`

### 4. 启用 Actions

1. 进入 Actions 标签页
2. 点击 "I understand my workflows, go ahead and enable them"
3. 手动运行一次 "Daily RSS Digest" 测试

## 自定义

### 修改推送时间

编辑 `.github/workflows/rss-digest.yml`：

```yaml
schedule:
  # 每天早上 8:00 (北京时间 = UTC 0:00)
  - cron: '0 0 * * *'
```

### 添加更多 RSS 源

编辑 `config/feeds.json`，推荐源：

| 分类 | 源 | URL |
|------|-----|-----|
| AI | 量子位 | `https://www.qbitai.com/rss` |
| AI | 机器之心 | `https://www.jiqizhixin.com/rss` |
| AI | OpenAI | `https://openai.com/blog/rss.xml` |
| 科技 | 36 氪 | `https://36kr.com/feed` |
| 科技 | 钛媒体 | `https://www.tmtpost.com/rss.xml` |
| 科技 | 少数派 | `https://sspai.com/feed` |
| 科技 | TechCrunch | `https://techcrunch.com/feed/` |

### 推送到其他平台

修改 `scripts/fetch_and_push.py` 中的 `push_to_feishu()` 函数即可。

## 成本

- GitHub Actions：每月 2000 分钟免费（本项目每次运行<1 分钟，每天 1 次 = 每月 30 分钟）
- 服务器：$0
- 维护：几乎为零

## 许可证

MIT
