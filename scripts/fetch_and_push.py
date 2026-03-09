#!/usr/bin/env python3
"""
RSS 每日摘要 - 使用可靠的免费模型
"""

import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import os
import re
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# OpenRouter API 配置 - 使用确认免费且可靠的模型
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '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')
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
# 使用确认免费的 Google Gemma 模型
OPENROUTER_MODEL = "google/gemma-2-9b-it:free"

def load_feeds():
    config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def ai_translate_and_summarize(title, content):
    """AI 翻译 + 总结"""
    if not content:
        return f"📰 {title}"
    
    # 清理 HTML
    clean_content = re.sub(r'<[^>]+>', '', content)
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
    
    # 检测是否英文
    is_english = not re.search(r'[\u4e00-\u9fff]', title + clean_content)
    
    # 中文直接返回
    if not is_english:
        clean_content = re.sub(r'📰', '', clean_content)
        return clean_content[:120] + ('...' if len(clean_content) > 120 else '')
    
    # 截取
    clean_content = clean_content[:600]
    
    # 简单直接的提示词
    prompt = f"""Translate this English news to Chinese and summarize in 60-100 Chinese characters:

Title: {title}
Content: {clean_content}

Output ONLY the Chinese summary, no other text:"""

    try:
        response = requests.post(
            OPENROUTER_ENDPOINT,
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/SuperAvenger/rss-digest',
                'X-Title': 'RSS Digest'
            },
            json={
                'model': OPENROUTER_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 150,
                'temperature': 0.3
            },
            timeout=30
        )
        
        # 打印响应状态
        if response.status_code != 200:
            print(f"  ❌ API 失败：{response.status_code}")
            print(f"  响应：{response.text[:200]}")
            return f"[API 错误{response.status_code}] {title[:40]}..."
        
        result = response.json()
        
        if 'choices' not in result or not result['choices']:
            print(f"  ❌ 响应格式错误：{result}")
            return f"[格式错误] {title[:40]}..."
        
        summary = result['choices'][0]['message']['content'].strip()
        summary = summary.strip('"\'')
        
        # 验证：如果还是英文，说明翻译失败
        if len(summary) > 20 and re.search(r'[A-Za-z]{10,}', summary):
            print(f"  ⚠️ 翻译失败，返回英文")
            return f"[翻译失败] {title[:40]}..."
        
        if len(summary) > 120:
            summary = summary[:117] + '...'
        
        return summary
        
    except requests.exceptions.Timeout:
        print(f"  ⏱️ 请求超时")
        return f"[超时] {title[:40]}..."
    except Exception as e:
        print(f"  ❌ 异常：{e}")
        return f"[错误] {title[:40]}..."

def is_quality_article(title, summary, config):
    if len(title) < config.get('min_title_length', 8):
        return False
    blacklist = config.get('blacklist_keywords', [])
    text = title + ' ' + (summary or '')
    for keyword in blacklist:
        if keyword.lower() in text.lower():
            return False
    return True

def match_keywords(title, summary, keywords):
    if not keywords:
        return 1
    text = (title + ' ' + (summary or '')).lower()
    matches = sum(1 for kw in keywords if kw.lower() in text)
    if matches >= 1:
        return 0.5 + (matches / len(keywords)) * 0.5
    return matches / len(keywords) if keywords else 0

def fetch_feed_with_headers(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except Exception as e:
        print(f"  ❌ 抓取失败：{e}")
        return feedparser.parse(url)

def fetch_feeds(feeds_config):
    articles = []
    settings = feeds_config.get('settings', {})
    total_fetched = 0
    category_stats = {}
    
    print(f"\n🤖 AI 模型：{OPENROUTER_MODEL}")
    print(f"   状态：免费")
    print("=" * 70)
    
    for feed_config in feeds_config['feeds']:
        try:
            print(f"\n📰 抓取：{feed_config['name']}")
            feed = fetch_feed_with_headers(feed_config['url'])
            
            if not feed.entries:
                print(f"  ⚠️ 无内容")
                continue
            
            weight = feed_config.get('weight', 5)
            keywords = feed_config.get('keywords', [])
            category = feed_config['category']
            is_english = feed_config.get('language', 'zh') == 'en'
            
            if category not in category_stats:
                category_stats[category] = {'fetched': 0, 'passed': 0, 'failed': 0, 'ai_ok': 0, 'ai_fail': 0}
            
            for entry in feed.entries[:settings.get('max_items_per_feed', 15)]:
                total_fetched += 1
                category_stats[category]['fetched'] += 1
                
                title = entry.title
                summary = entry.get('summary', '')
                
                if not is_quality_article(title, summary, settings):
                    category_stats[category]['failed'] += 1
                    continue
                
                match_score = match_keywords(title, summary, keywords)
                
                if is_english:
                    print(f"  🌐 {title[:30]}...")
                
                brief = ai_translate_and_summarize(title, summary)
                
                # 统计 AI 成功/失败
                if brief.startswith('['):
                    category_stats[category]['ai_fail'] += 1
                else:
                    category_stats[category]['ai_ok'] += 1
                
                time.sleep(0.2)
                
                articles.append({
                    'category': category,
                    'source': feed_config['name'],
                    'title': title,
                    'link': entry.link,
                    'summary': brief,
                    'weight': weight,
                    'match_score': match_score,
                    'score': weight * match_score,
                })
                category_stats[category]['passed'] += 1
                
        except Exception as e:
            print(f"❌ 抓取失败 {feed_config['name']}: {e}")
    
    # 打印统计
    print("\n" + "=" * 70)
    print("📊 详细统计:")
    print("=" * 70)
    for cat, stats in category_stats.items():
        status = "✅" if stats['passed'] > 0 else "❌"
        print(f"{status} {cat}:")
        print(f"   抓取{stats['fetched']}条 → 通过{stats['passed']}条 → 过滤{stats['failed']}条")
        print(f"   AI 成功{stats['ai_ok']}条 → AI 失败{stats['ai_fail']}条")
    
    # 分组排序
    by_category = {}
    for article in articles:
        cat = article['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(article)
    
    final_articles = []
    for cat, items in by_category.items():
        items.sort(key=lambda x: x['score'], reverse=True)
        final_articles.extend(items[:15])
    
    total_passed = sum(len(items) for items in by_category.values())
    ai_ok_total = sum(s['ai_ok'] for s in category_stats.values())
    ai_fail_total = sum(s['ai_fail'] for s in category_stats.values())
    
    print(f"\n✅ 总计：{total_fetched} 条 → {total_passed} 条")
    print(f"🤖 AI 成功：{ai_ok_total}条 → AI 失败：{ai_fail_total}条")
    print("=" * 70)
    
    return final_articles

def format_message(articles):
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
    
    category_order = ['🤖 AI 资讯', '💻 科技资讯', '📈 财经资讯', '🌍 国际新闻', '📡 通信运营商', '🔍 审计领域']
    
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
    lines.append(f"💡 _AI 翻译 + 总结 (Google Gemma 2 9B)_")
    
    return '\n'.join(lines)

def push_to_feishu(message):
    webhook = os.environ.get('FEISHU_WEBHOOK')
    print(f"\n🔍 Webhook: {'✅' if webhook else '❌'}")
    
    if not webhook:
        print("⚠️ 未配置")
        print("\n" + message[:500] + "...")
        return
    
    try:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": "📰 每日新闻摘要"}, "template": "blue"},
                "elements": [{"tag": "markdown", "content": message}]
            }
        }
        
        response = requests.post(webhook, json=payload, timeout=30, headers=HEADERS)
        print(f"   响应：{response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ 推送成功")
        else:
            print(f"❌ 推送失败：{response.status_code}")
            print(f"   {response.text}")
    except Exception as e:
        print(f"❌ 推送异常：{e}")

def main():
    print("=" * 70)
    print("🚀 RSS 智能摘要")
    print("=" * 70)
    
    config = load_feeds()
    print(f"📋 {len(config['feeds'])} 个 RSS 源")
    print(f"📊 每源最多：{config['settings'].get('max_items_per_feed', 15)} 条")
    print(f"🤖 模型：{OPENROUTER_MODEL}")
    print("=" * 70)
    
    articles = fetch_feeds(config)
    
    if not articles:
        print("⚠️ 没有文章")
        return
    
    message = format_message(articles)
    push_to_feishu(message)
    
    print("=" * 70)
    print("✅ 完成")
    print("=" * 70)

if __name__ == '__main__':
    main()
