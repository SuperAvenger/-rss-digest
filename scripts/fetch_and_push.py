#!/usr/bin/env python3
"""
RSS 每日摘要 - 智能筛选 + 翻译 + 完整分类版本
"""

import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import os
import re
import time

# 设置 User-Agent，避免被拒绝
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def load_feeds():
    """加载 RSS 源配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def translate_text(text, target_lang='zh'):
    """
    翻译英文到中文
    使用 MyMemory 免费翻译 API
    """
    if not text:
        return text
    
    # 检查是否包含中文
    if re.search(r'[\u4e00-\u9fff]', text):
        return text
    
    try:
        text_to_translate = text[:500]
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": text_to_translate,
            "langpair": "en|zh"
        }
        
        response = requests.get(url, params=params, timeout=10, headers=HEADERS)
        
        if response.status_code == 200:
            result = response.json()
            translated = result.get('responseData', {}).get('translatedText', text)
            
            if len(text) > 500:
                return translated + "..."
            return translated
        
        return text
        
    except Exception as e:
        print(f"  ⚠️ 翻译失败：{e}")
        return text

def is_quality_article(title, summary, config):
    """判断文章质量"""
    if len(title) < config.get('min_title_length', 8):
        return False
    
    blacklist = config.get('blacklist_keywords', [])
    text = title + ' ' + (summary or '')
    text_lower = text.lower()
    
    for keyword in blacklist:
        if keyword.lower() in text_lower:
            return False
    
    return True

def match_keywords(title, summary, keywords):
    """关键词匹配"""
    if not keywords:
        return 1
    
    text = (title + ' ' + (summary or '')).lower()
    matches = sum(1 for kw in keywords if kw.lower() in text)
    
    if matches >= 1:
        return 0.5 + (matches / len(keywords)) * 0.5
    
    return matches / len(keywords) if keywords else 0

def generate_summary(title, summary, max_length=100):
    """生成简短摘要"""
    if summary:
        clean_summary = re.sub(r'<[^>]+>', '', summary)
        clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()
        clean_summary = re.sub(r'作者 [丨|].*?编辑 [丨|].*?\s*', '', clean_summary)
        clean_summary = re.sub(r'作者 [丨|].*?\s*', '', clean_summary)
        
        if len(clean_summary) > max_length:
            return clean_summary[:max_length-3] + '...'
        return clean_summary if clean_summary else f"📰 {title}"
    
    return f"📰 {title[:60]}..." if len(title) > 60 else f"📰 {title}"

def fetch_feed_with_headers(url):
    """
    使用自定义 Headers 抓取 RSS
    避免被服务器拒绝
    """
    try:
        # 先下载内容
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # 用 feedparser 解析
        feed = feedparser.parse(response.content)
        return feed
    except Exception as e:
        print(f"  ❌ 抓取失败：{e}")
        return feedparser.parse(url)  # 回退到默认方式

def fetch_feeds(feeds_config):
    """抓取所有 RSS 源"""
    articles = []
    settings = feeds_config.get('settings', {})
    total_fetched = 0
    category_stats = {}
    
    for feed_config in feeds_config['feeds']:
        try:
            print(f"\n📰 抓取：{feed_config['name']} ({feed_config['category']})")
            
            # 使用自定义 Headers 抓取
            feed = fetch_feed_with_headers(feed_config['url'])
            
            if not feed.entries:
                print(f"  ⚠️ 无内容")
                continue
            
            weight = feed_config.get('weight', 5)
            keywords = feed_config.get('keywords', [])
            category = feed_config['category']
            is_english = feed_config.get('language', 'zh') == 'en'
            
            if category not in category_stats:
                category_stats[category] = {'fetched': 0, 'passed': 0, 'failed': 0}
            
            for entry in feed.entries[:settings.get('max_items_per_feed', 15)]:
                total_fetched += 1
                category_stats[category]['fetched'] += 1
                
                title = entry.title
                summary = entry.get('summary', '')
                
                # 质量筛选
                if not is_quality_article(title, summary, settings):
                    category_stats[category]['failed'] += 1
                    continue
                
                # 关键词匹配
                match_score = match_keywords(title, summary, keywords)
                
                # 翻译英文内容
                if is_english:
                    title = translate_text(title)
                    summary = translate_text(summary)
                    time.sleep(0.1)
                
                short_summary = generate_summary(title, summary)
                
                article = {
                    'category': category,
                    'source': feed_config['name'],
                    'title': title,
                    'link': entry.link,
                    'summary': short_summary,
                    'published': entry.get('published', ''),
                    'weight': weight,
                    'match_score': match_score,
                    'score': weight * match_score,
                }
                articles.append(article)
                category_stats[category]['passed'] += 1
                
        except Exception as e:
            print(f"❌ 抓取失败 {feed_config['name']}: {e}")
    
    # 打印统计
    print("\n" + "=" * 60)
    print("📊 分类统计:")
    print("=" * 60)
    for cat, stats in category_stats.items():
        status = "✅" if stats['passed'] > 0 else "❌"
        print(f"{status} {cat}: 抓取{stats['fetched']}条 → 通过{stats['passed']}条 → 过滤{stats['failed']}条")
    
    # 按分类分组
    by_category = {}
    for article in articles:
        cat = article['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(article)
    
    # 每类内按评分排序，取前 15 条
    final_articles = []
    for cat, items in by_category.items():
        items.sort(key=lambda x: x['score'], reverse=True)
        final_articles.extend(items[:15])
    
    total_passed = sum(len(items) for items in by_category.values())
    print(f"\n✅ 总计：{total_fetched} 条原始内容 → {total_passed} 条优质文章")
    print("=" * 60)
    
    return final_articles

def format_message(articles):
    """格式化为飞书消息"""
    if not articles:
        return "今日暂无符合条件的文章"
    
    by_category = {}
    for article in articles:
        cat = article['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(article)
    
    total_count = sum(len(items) for items in by_category.values())
    
    lines = [
        f"📰 **每日新闻摘要** ({datetime.now().strftime('%Y年%m月%d日')})",
        f"共筛选出 **{total_count}** 条优质内容",
        "=" * 50,
        ""
    ]
    
    category_order = [
        '🤖 AI 资讯',
        '💻 科技资讯',
        '📈 财经资讯',
        '🌍 国际新闻',
        '📡 通信运营商',
        '🔍 审计领域'
    ]
    
    for category in category_order:
        if category not in by_category:
            lines.append(f"\n{category} (0 条)")
            lines.append("-" * 40)
            lines.append("_今日暂无相关内容_")
            lines.append("")
            continue
        
        items = by_category[category]
        lines.append(f"\n{category} ({len(items)}条)")
        lines.append("-" * 40)
        
        for i, item in enumerate(items, 1):
            lines.append(f"\n**{i:2d}. {item['title']}**")
            lines.append(f"📍 {item['source']}")
            lines.append(f"💡 {item['summary']}")
            lines.append(f"🔗 [阅读原文]({item['link']})")
        
        lines.append("")
    
    lines.append("=" * 50)
    lines.append(f"💡 _智能筛选：过滤广告/推广/标题党，英文内容自动翻译_")
    
    return '\n'.join(lines)

def push_to_feishu(message):
    """推送到飞书"""
    webhook = os.environ.get('FEISHU_WEBHOOK')
    
    print(f"\n🔍 调试信息:")
    print(f"   Webhook 配置：{'✅ 已配置' if webhook else '❌ 未配置'}")
    if webhook:
        print(f"   Webhook 前缀：{webhook[:50]}...")
    
    if not webhook:
        print("⚠️ 未配置飞书 Webhook，仅打印消息")
        print("\n" + message[:500] + "...")
        return
    
    try:
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
        
        print(f"   发送请求到飞书...")
        response = requests.post(webhook, json=payload, timeout=30, headers=HEADERS)
        
        print(f"   响应状态码：{response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 飞书推送成功")
            print(f"   响应：{result}")
        else:
            print(f"❌ 飞书推送失败：{response.status_code}")
            print(f"   响应内容：{response.text}")
            
    except Exception as e:
        print(f"❌ 推送异常：{e}")

def main():
    print("=" * 60)
    print("🚀 RSS 智能摘要 - 开始抓取")
    print("=" * 60)
    
    config = load_feeds()
    print(f"📋 共配置 {len(config['feeds'])} 个 RSS 源")
    print(f"📊 筛选规则:")
    print(f"   - 每源最多：{config['settings'].get('max_items_per_feed', 15)} 条")
    print(f"   - 每类最多：15 条")
    print(f"   - 最小标题长度：{config['settings'].get('min_title_length', 8)}")
    print(f"   - 黑名单：{', '.join(config['settings'].get('blacklist_keywords', []))}")
    print(f"   - 英文翻译：✅ 开启")
    print("=" * 60)
    
    articles = fetch_feeds(config)
    
    if not articles:
        print("⚠️ 没有符合条件的文章")
        return
    
    message = format_message(articles)
    push_to_feishu(message)
    
    print("=" * 60)
    print("✅ 完成")
    print("=" * 60)

if __name__ == '__main__':
    main()
