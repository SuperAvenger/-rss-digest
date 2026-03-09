#!/usr/bin/env python3
"""
RSS 每日摘要 - GitHub Actions 版本
抓取 RSS → 格式化 → 推送到飞书
"""

import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import os

def load_feeds():
    """加载 RSS 源配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_feeds(feeds_config):
    """抓取所有 RSS 源"""
    articles = []
    
    for feed_config in feeds_config['feeds']:
        try:
            print(f"📰 抓取：{feed_config['name']}")
            feed = feedparser.parse(feed_config['url'])
            
            for entry in feed.entries[:feeds_config['settings']['max_items_per_feed']]:
                article = {
                    'category': feed_config['category'],
                    'source': feed_config['name'],
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', ''),
                }
                articles.append(article)
                
                # 限制总数
                if len(articles) >= feeds_config['settings']['max_total_items']:
                    break
                    
        except Exception as e:
            print(f"❌ 抓取失败 {feed_config['name']}: {e}")
        
        # 限制总数
        if len(articles) >= feeds_config['settings']['max_total_items']:
            break
    
    return articles

def format_message(articles):
    """格式化为飞书消息"""
    if not articles:
        return "今日暂无新文章"
    
    # 按分类分组
    by_category = {}
    for article in articles:
        cat = article['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(article)
    
    # 构建消息
    lines = [
        f"📰 **每日新闻摘要** ({datetime.now().strftime('%Y年%m月%d日')})",
        "=" * 50,
        ""
    ]
    
    for category, items in by_category.items():
        lines.append(f"\n📌 **{category}**")
        lines.append("-" * 30)
        
        for item in items[:3]:  # 每类最多 3 条
            lines.append(f"• **{item['source']}**")
            lines.append(f"  {item['title']}")
            lines.append(f"  🔗 [阅读原文]({item['link']})")
            lines.append("")
    
    lines.append("\n" + "=" * 50)
    lines.append("💡 _以上为 AI 筛选的重要资讯_")
    
    return '\n'.join(lines)

def push_to_feishu(message):
    """推送到飞书"""
    webhook = os.environ.get('FEISHU_WEBHOOK')
    
    if not webhook:
        print("⚠️ 未配置飞书 Webhook，仅打印消息")
        print("\n" + message)
        return
    
    try:
        # 飞书文本消息格式
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📰 每日新闻摘要"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": message
                    }
                ]
            }
        }
        
        response = requests.post(webhook, json=payload, timeout=30)
        
        if response.status_code == 200:
            print("✅ 飞书推送成功")
        else:
            print(f"❌ 飞书推送失败：{response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ 推送异常：{e}")

def main():
    print("🚀 开始抓取 RSS 新闻")
    print("=" * 50)
    
    # 加载配置
    config = load_feeds()
    print(f"📋 共配置 {len(config['feeds'])} 个 RSS 源")
    
    # 抓取
    articles = fetch_feeds(config)
    print(f"📰 抓取到 {len(articles)} 条新文章")
    
    if not articles:
        print("⚠️ 没有新文章")
        return
    
    # 格式化
    message = format_message(articles)
    
    # 推送
    push_to_feishu(message)
    
    print("=" * 50)
    print("✅ 完成")

if __name__ == '__main__':
    main()
