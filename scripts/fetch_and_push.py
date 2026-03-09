#!/usr/bin/env python3
"""
RSS 每日摘要 - AI 翻译 + 总结版本
使用：OpenRouter (google/gemma-2-9b-it:free 或 qwen/qwen-2.5-72b-instruct)
"""

import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import os
import re
import time

# 设置 User-Agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# OpenRouter API 配置 - 改用支持中文更好的模型
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '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')
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
# 改用 Qwen 模型（对中文支持更好）
OPENROUTER_MODEL = "qwen/qwen-2.5-72b-instruct"

def load_feeds():
    """加载 RSS 源配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def ai_translate_and_summarize(title, content):
    """
    调用 OpenRouter API 翻译 + 总结
    强制要求翻译为中文
    """
    if not content:
        return f"📰 {title}"
    
    # 清理 HTML 标签
    clean_content = re.sub(r'<[^>]+>', '', content)
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
    
    # 检测是否英文
    is_english = not re.search(r'[\u4e00-\u9fff]', title + clean_content)
    
    # 如果不是英文，直接总结
    if not is_english:
        # 清理无意义内容
        clean_content = re.sub(r'📰', '', clean_content)
        if len(clean_content) > 10:
            return clean_content[:120] + ('...' if len(clean_content) > 120 else '')
        return title
    
    # 截取前 800 字
    clean_content = clean_content[:800]
    
    # 强制翻译提示词
    prompt = f"""你是一个专业的新闻翻译和编辑。你的任务是将英文新闻翻译成简洁的中文摘要。

【英文原文】
标题：{title}
内容：{clean_content}

【任务要求】
1. 必须将标题和内容翻译成中文
2. 用 60-100 字概括核心内容
3. 保留关键数据、人名、公司名
4. 输出必须是纯中文，不要保留英文句子
5. 不要添加"这篇文章"、"该新闻"等冗余词

【输出格式】
直接输出翻译后的中文摘要，不要有其他说明。

【中文翻译】"""

    try:
        response = requests.post(
            OPENROUTER_ENDPOINT,
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/SuperAvenger/rss-digest',
                'X-Title': 'RSS Daily Digest'
            },
            json={
                'model': OPENROUTER_MODEL,
                'messages': [
                    {'role': 'system', 'content': '你是一个专业的新闻翻译。你必须将英文内容翻译成中文。如果用户输入英文，你必须用中文回复。'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 200,
                'temperature': 0.3
            },
            timeout=40
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result['choices'][0]['message']['content'].strip()
            
            # 清理引号
            summary = summary.strip('"\'')
            
            # 验证：如果还是英文，说明翻译失败
            if re.search(r'[A-Za-z]{20,}', summary):
                print(f"  ⚠️ 翻译失败，返回的仍是英文")
                # 尝试简单翻译
                return f"[英文] {title[:60]}..."
            
            # 长度控制
            if len(summary) > 120:
                summary = summary[:117] + '...'
            
            return summary
        else:
            print(f"  ⚠️ API 失败：{response.status_code}")
            print(f"  响应：{response.text[:200]}")
            return f"[API 错误] {title[:50]}..."
            
    except Exception as e:
        print(f"  ⚠️ 异常：{e}")
        return f"[错误] {title[:50]}..."

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

def fetch_feed_with_headers(url):
    """使用自定义 Headers 抓取 RSS"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        return feed
    except Exception as e:
        print(f"  ❌ 抓取失败：{e}")
        return feedparser.parse(url)

def fetch_feeds(feeds_config):
    """抓取所有 RSS 源"""
    articles = []
    settings = feeds_config.get('settings', {})
    total_fetched = 0
    category_stats = {}
    
    print(f"\n🤖 AI 翻译：使用 OpenRouter ({OPENROUTER_MODEL})")
    print(f"   模型特点：支持中文，翻译质量好")
    print(f"   免费额度：充足")
    print("=" * 70)
    
    for feed_config in feeds_config['feeds']:
        try:
            print(f"\n📰 抓取：{feed_config['name']} ({feed_config['category']})")
            
            feed = fetch_feed_with_headers(feed_config['url'])
            
            if not feed.entries:
                print(f"  ⚠️ 无内容")
                continue
            
            weight = feed_config.get('weight', 5)
            keywords = feed_config.get('keywords', [])
            category = feed_config['category']
            is_english = feed_config.get('language', 'zh') == 'en'
            
            if category not in category_stats:
                category_stats[category] = {'fetched': 0, 'passed': 0, 'failed': 0, 'ai_processed': 0}
            
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
                
                # AI 翻译 + 总结
                if is_english:
                    print(f"  🤖 翻译：{title[:30]}...")
                else:
                    print(f"  📝 总结：{title[:30]}...")
                
                brief = ai_translate_and_summarize(title, summary)
                category_stats[category]['ai_processed'] += 1
                
                # 短暂延迟
                time.sleep(0.2)
                
                article = {
                    'category': category,
                    'source': feed_config['name'],
                    'title': title,
                    'link': entry.link,
                    'summary': brief,
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
    print("\n" + "=" * 70)
    print("📊 分类统计:")
    print("=" * 70)
    for cat, stats in category_stats.items():
        status = "✅" if stats['passed'] > 0 else "❌"
        print(f"{status} {cat}: 抓取{stats['fetched']}条 → 通过{stats['passed']}条 → AI 处理{stats['ai_processed']}条")
    
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
    print(f"\n✅ 总计：{total_fetched} 条 → {total_passed} 条优质文章")
    print(f"🤖 AI 处理：{sum(s['ai_processed'] for s in category_stats.values())} 条")
    print("=" * 70)
    
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
    lines.append(f"💡 _AI 翻译 + 智能总结 (Qwen 72B 模型)_")
    
    return '\n'.join(lines)

def push_to_feishu(message):
    """推送到飞书"""
    webhook = os.environ.get('FEISHU_WEBHOOK')
    
    print(f"\n🔍 推送调试:")
    print(f"   Webhook: {'✅ 已配置' if webhook else '❌ 未配置'}")
    
    if not webhook:
        print("⚠️ 未配置 Webhook，仅打印")
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
        
        print(f"   发送请求...")
        response = requests.post(webhook, json=payload, timeout=30, headers=HEADERS)
        
        print(f"   响应：{response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 飞书推送成功")
            print(f"   响应：{result}")
        else:
            print(f"❌ 飞书推送失败：{response.status_code}")
            print(f"   内容：{response.text}")
            
    except Exception as e:
        print(f"❌ 推送异常：{e}")

def main():
    print("=" * 70)
    print("🚀 RSS 智能摘要 - 开始抓取")
    print("=" * 70)
    
    config = load_feeds()
    print(f"📋 共配置 {len(config['feeds'])} 个 RSS 源")
    print(f"📊 筛选规则:")
    print(f"   - 每源最多：{config['settings'].get('max_items_per_feed', 15)} 条")
    print(f"   - 每类最多：15 条")
    print(f"   - 最小标题长度：{config['settings'].get('min_title_length', 8)}")
    print(f"   - 黑名单：{', '.join(config['settings'].get('blacklist_keywords', []))}")
    print(f"   - AI 模型：{OPENROUTER_MODEL}")
    print("=" * 70)
    
    articles = fetch_feeds(config)
    
    if not articles:
        print("⚠️ 没有符合条件的文章")
        return
    
    message = format_message(articles)
    push_to_feishu(message)
    
    print("=" * 70)
    print("✅ 完成")
    print("=" * 70)

if __name__ == '__main__':
    main()
