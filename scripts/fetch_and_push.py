#!/usr/bin/env python3
"""
RSS 每日摘要 - 智能筛选 + 总结版本
功能：
1. 按权重和关键词筛选内容
2. 过滤低质量文章（广告、推广等）
3. 生成简短摘要
4. 按分类整理推送
"""

import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import os
import re

def load_feeds():
    """加载 RSS 源配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def is_quality_article(title, summary, config):
    """
    判断文章质量，过滤低质内容
    """
    # 标题太短
    if len(title) < config.get('min_title_length', 10):
        return False
    
    # 黑名单关键词过滤
    blacklist = config.get('blacklist_keywords', [])
    text = title + ' ' + (summary or '')
    
    for keyword in blacklist:
        if keyword in text:
            return False
    
    # 标题党特征过滤
    clickbait_patterns = [
        r'震惊[！!]',
        r'重磅[！!]',
        r'刚刚[！!]',
        r'速看',
        r'删前速看',
        r'不转不是',
    ]
    
    for pattern in clickbait_patterns:
        if re.search(pattern, title):
            return False
    
    return True

def match_keywords(title, summary, keywords):
    """
    检查文章是否匹配关键词
    返回匹配度分数
    """
    if not keywords:
        return 1  # 没有关键词要求，默认匹配
    
    text = (title + ' ' + (summary or '')).lower()
    matches = sum(1 for kw in keywords if kw.lower() in text)
    
    return matches / len(keywords) if keywords else 1

def generate_summary(title, summary, max_length=80):
    """
    生成简短摘要
    优先用文章摘要，没有则从标题生成
    """
    if summary:
        # 清理 HTML 标签
        clean_summary = re.sub(r'<[^>]+>', '', summary)
        clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()
        
        # 截取
        if len(clean_summary) > max_length:
            return clean_summary[:max_length-3] + '...'
        return clean_summary
    
    # 没有摘要时，简单描述
    return f"📰 {title[:50]}..." if len(title) > 50 else f"📰 {title}"

def fetch_feeds(feeds_config):
    """
    抓取所有 RSS 源，带筛选和评分
    """
    articles = []
    settings = feeds_config.get('settings', {})
    
    for feed_config in feeds_config['feeds']:
        try:
            print(f"📰 抓取：{feed_config['name']}")
            feed = feedparser.parse(feed_config['url'])
            
            if not feed.entries:
                print(f"  ⚠️ 无内容")
                continue
            
            weight = feed_config.get('weight', 5)
            keywords = feed_config.get('keywords', [])
            
            for entry in feed.entries[:settings.get('max_items_per_feed', 10)]:
                title = entry.title
                summary = entry.get('summary', '')
                
                # 质量筛选
                if not is_quality_article(title, summary, settings):
                    print(f"  ⏭️  过滤低质：{title[:30]}...")
                    continue
                
                # 关键词匹配
                match_score = match_keywords(title, summary, keywords)
                if match_score < 0.3:  # 匹配度低于 30% 的过滤
                    print(f"  ⏭️  关键词不匹配：{title[:30]}...")
                    continue
                
                # 生成摘要
                short_summary = generate_summary(title, summary)
                
                article = {
                    'category': feed_config['category'],
                    'source': feed_config['name'],
                    'title': title,
                    'link': entry.link,
                    'summary': short_summary,
                    'published': entry.get('published', ''),
                    'weight': weight,
                    'match_score': match_score,
                    'score': weight * match_score,  # 综合评分
                }
                articles.append(article)
                
        except Exception as e:
            print(f"❌ 抓取失败 {feed_config['name']}: {e}")
    
    # 按综合评分排序
    articles.sort(key=lambda x: x['score'], reverse=True)
    
    # 限制总数
    max_total = settings.get('max_total_items', 50)
    articles = articles[:max_total]
    
    print(f"✅ 抓取到 {len(articles)} 条优质文章（从 {sum(len(f.get('entries', [])) for f in feeds_config['feeds'])} 条中筛选）")
    
    return articles

def format_message(articles):
    """
    格式化为飞书消息（带摘要）
    """
    if not articles:
        return "今日暂无符合条件的文章"
    
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
        f"共筛选出 {len(articles)} 条优质内容",
        "=" * 50,
        ""
    ]
    
    # 分类顺序
    category_order = ['🤖 AI 资讯', '💻 科技资讯', '📈 财经资讯', '🌍 国际新闻', '📡 通信运营商', '🔍 审计领域']
    
    for category in category_order:
        if category not in by_category:
            continue
        
        items = by_category[category][:5]  # 每类最多 5 条
        lines.append(f"\n{category}")
        lines.append("-" * 40)
        
        for i, item in enumerate(items, 1):
            # 标题
            lines.append(f"\n**{i}. {item['title']}**")
            # 来源
            lines.append(f"📍 {item['source']}")
            # 摘要
            lines.append(f"💡 {item['summary']}")
            # 链接
            lines.append(f"🔗 [阅读原文]({item['link']})")
        
        lines.append("")
    
    lines.append("=" * 50)
    lines.append(f"💡 _智能筛选：过滤广告/推广/标题党，只保留高质量内容_")
    
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
    print("=" * 60)
    print("🚀 RSS 智能摘要 - 开始抓取")
    print("=" * 60)
    
    # 加载配置
    config = load_feeds()
    print(f"📋 共配置 {len(config['feeds'])} 个 RSS 源")
    print(f"📊 筛选规则:")
    print(f"   - 每源最多：{config['settings'].get('max_items_per_feed', 10)} 条")
    print(f"   - 总数限制：{config['settings'].get('max_total_items', 50)} 条")
    print(f"   - 最小标题长度：{config['settings'].get('min_title_length', 10)}")
    print(f"   - 黑名单：{', '.join(config['settings'].get('blacklist_keywords', []))}")
    print("=" * 60)
    
    # 抓取 + 筛选
    articles = fetch_feeds(config)
    
    if not articles:
        print("⚠️ 没有符合条件的文章")
        return
    
    # 格式化
    message = format_message(articles)
    
    # 推送
    push_to_feishu(message)
    
    print("=" * 60)
    print("✅ 完成")
    print("=" * 60)

if __name__ == '__main__':
    main()
