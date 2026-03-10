#!/usr/bin/env python3
"""
RSS 每日摘要 - Gemini 翻译
GitHub Actions 在国外，可直接访问 Google AI Studio
"""

import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import os
import re
import time

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# Gemini 配置（GitHub Actions 可访问）
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

DETAILED_LOGS = []


def load_feeds():
    config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def translate_with_gemini(title, content):
    """Gemini 翻译（无思考过程，直接输出）"""
    if not GEMINI_API_KEY:
        return None
    
    prompt = f"Translate this news to Chinese summary (60-100 characters). Output ONLY the Chinese summary, no other text:\n\nTitle: {title}\nContent: {content[:400]}\n\nChinese summary:"
    
    try:
        resp = requests.post(
            f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 200, "temperature": 0.3}
            },
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            if 'candidates' in result and result['candidates']:
                summary = result['candidates'][0]['content']['parts'][0]['text'].strip()
                summary = summary.strip('"\'')
                if re.search(r'[\u4e00-\u9fff]', summary):
                    return summary[:120]
        return None
    except Exception as e:
        return None


def ai_translate_and_summarize(title, content, index=0):
    """AI 翻译"""
    if not content:
        return f"📰 {title}"
    
    clean_content = re.sub(r'<[^>]+>', '', content)
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
    
    # 中文内容直接返回
    if re.search(r'[\u4e00-\u9fff]', title + clean_content):
        return clean_content[:120] + ('...' if len(clean_content) > 120 else '')
    
    clean_content = clean_content[:600]
    
    log_entry = {
        'index': index,
        'title': title,
        'timestamp': datetime.now().isoformat()
    }
    
    # 用 Gemini 翻译
    gemini_result = translate_with_gemini(title, clean_content)
    if gemini_result:
        log_entry['model'] = 'gemini'
        log_entry['success'] = True
        DETAILED_LOGS.append(log_entry)
        return gemini_result
    
    # 失败：保留英文原文
    log_entry['model'] = 'fallback'
    log_entry['success'] = False
    DETAILED_LOGS.append(log_entry)
    return f"[EN] {title}"


def is_quality_article(title, summary, config):
    if len(title) < config.get('min_title_length', 8):
        return False
    for keyword in config.get('blacklist_keywords', []):
        if keyword.lower() in (title + ' ' + (summary or '')).lower():
            return False
    return True


def match_keywords(title, summary, keywords):
    if not keywords:
        return 1
    text = (title + ' ' + (summary or '')).lower()
    matches = sum(1 for kw in keywords if kw.lower() in text)
    return 0.5 + (matches / len(keywords)) * 0.5 if matches >= 1 else 0


def fetch_feed_with_headers(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return feedparser.parse(resp.content)
    except Exception as e:
        print(f"  ❌ 抓取失败：{e}")
        return feedparser.parse(url)


def fetch_feeds(feeds_config):
    articles = []
    settings = feeds_config.get('settings', {})
    total_fetched = 0
    category_stats = {}
    
    print(f"\n🤖 翻译配置:")
    print(f"   模型：Gemini 2.0 Flash")
    print(f"   API Key: {'✅' if GEMINI_API_KEY else '❌'}")
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
            
            if category not in category_stats:
                category_stats[category] = {'fetched': 0, 'passed': 0, 'translated': 0, 'english': 0}
            
            article_index = 0
            
            for entry in feed.entries[:settings.get('max_items_per_feed', 15)]:
                total_fetched += 1
                category_stats[category]['fetched'] += 1
                article_index += 1
                
                title = entry.title
                summary = entry.get('summary', '')
                
                if not is_quality_article(title, summary, settings):
                    category_stats[category]['failed'] += 1
                    continue
                
                match_score = match_keywords(title, summary, keywords)
                
                is_en = feed_config.get('language', 'zh') == 'en'
                if is_en:
                    print(f"  🌐 [{article_index:2d}] {title[:40]}...")
                else:
                    print(f"  📝 [{article_index:2d}] {title[:40]}...")
                
                brief = ai_translate_and_summarize(title, summary, article_index)
                
                if brief.startswith('[EN]'):
                    category_stats[category]['english'] += 1
                    if is_en:
                        print(f"      ⚠️ 英文原文")
                else:
                    category_stats[category]['translated'] += 1
                    print(f"      ✅ {brief[:40]}...")
                
                time.sleep(0.1)
                
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
    
    # 统计
    print("\n" + "=" * 70)
    print("📊 分类统计:")
    for cat, stats in category_stats.items():
        print(f"{cat}: 抓取{stats['fetched']} → 通过{stats['passed']} → 翻译{stats['translated']} → 英文{stats['english']}")
    
    # API 统计
    gemini_ok = sum(1 for log in DETAILED_LOGS if log.get('model') == 'gemini' and log.get('success'))
    failed = sum(1 for log in DETAILED_LOGS if not log.get('success'))
    
    print(f"\n📝 API 统计:")
    print(f"   Gemini 成功：{gemini_ok} 次")
    print(f"   降级英文：{failed} 次")
    
    # 保存日志
    log_file = Path(__file__).parent.parent / 'detailed_api_logs.json'
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(DETAILED_LOGS, f, ensure_ascii=False, indent=2)
    print(f"\n📄 日志已保存：{log_file}")
    
    # 排序
    by_category = {}
    for article in articles:
        by_category.setdefault(article['category'], []).append(article)
    
    final_articles = []
    for cat, items in by_category.items():
        items.sort(key=lambda x: x['score'], reverse=True)
        final_articles.extend(items[:15])
    
    print(f"\n✅ 总计：{total_fetched} → {len(final_articles)}")
    return final_articles


def format_message(articles):
    if not articles:
        return "今日暂无内容"
    
    by_category = {}
    for article in articles:
        by_category.setdefault(article['category'], []).append(article)
    
    lines = [
        f"📰 **每日新闻摘要** ({datetime.now().strftime('%Y年%m月%d日')})",
        f"共 **{len(articles)}** 条",
        "=" * 50,
        ""
    ]
    
    for category in ['🤖 AI 资讯', '💻 科技资讯', '📈 财经资讯', '🌍 国际新闻', '📡 通信运营商', '🔍 审计领域']:
        items = by_category.get(category, [])
        lines.append(f"\n{category} ({len(items)}条)")
        lines.append("-" * 40)
        
        for i, item in enumerate(items, 1):
            lines.append(f"\n**{i:2d}. {item['title']}**")
            lines.append(f"📍 {item['source']}")
            lines.append(f"💡 {item['summary']}")
            lines.append(f"🔗 [阅读原文]({item['link']})")
    
    lines.append("\n" + "=" * 50)
    return '\n'.join(lines)


def push_to_feishu(message):
    webhook = os.environ.get('FEISHU_WEBHOOK')
    if not webhook:
        print("⚠️ 未配置飞书 Webhook")
        print(message[:500])
        return
    
    try:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": "📰 每日新闻摘要"}, "template": "blue"},
                "elements": [{"tag": "markdown", "content": message}]
            }
        }
        resp = requests.post(webhook, json=payload, timeout=30)
        print(f"飞书推送：{resp.status_code}")
        if resp.status_code == 200:
            print("✅ 推送成功！")
        else:
            print(f"❌ 推送失败：{resp.text[:100]}")
    except Exception as e:
        print(f"推送失败：{e}")


def main():
    print("=" * 70)
    print("🚀 RSS 智能摘要 - Gemini 翻译")
    print("=" * 70)
    
    config = load_feeds()
    print(f"📋 {len(config['feeds'])} 个 RSS 源")
    
    articles = fetch_feeds(config)
    if not articles:
        print("⚠️ 没有文章")
        return
    
    message = format_message(articles)
    push_to_feishu(message)
    
    print("=" * 70)
    print("✅ 完成")


if __name__ == '__main__':
    main()
