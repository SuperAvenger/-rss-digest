#!/usr/bin/env python3
"""
RSS 每日摘要 - 智能筛选 + 翻译 + 完整分类版本
功能：
1. 按权重和关键词筛选内容
2. 过滤低质量文章（广告、推广等）
3. 英文内容自动翻译
4. 每个分类显示 10-15 条
5. 按重要性排序
"""

import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import os
import re
import time

def load_feeds():
    """加载 RSS 源配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def translate_text(text, target_lang='zh'):
    """
    翻译英文到中文
    使用 MyMemory 免费翻译 API（无需 key，每日 5000 字）
    """
    if not text:
        return text
    
    # 检查是否包含中文，如果有则不需要翻译
    if re.search(r'[\u4e00-\u9fff]', text):
        return text
    
    try:
        # 截取前 500 字翻译（避免超限）
        text_to_translate = text[:500]
        
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": text_to_translate,
            "langpair": "en|zh"
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            translated = result.get('responseData', {}).get('translatedText', text)
            
            # 如果原文超过 500 字，追加省略号
            if len(text) > 500:
                return translated + "..."
            return translated
        
        return text  # 翻译失败返回原文
        
    except Exception as e:
        print(f"  ⚠️ 翻译失败：{e}")
        return text  # 翻译失败返回原文

def is_quality_article(title, summary, config):
    """
    判断文章质量，过滤低质内容
    """
    # 标题太短
    if len(title) < config.get('min_title_length', 8):  # 降低到 8 字
        return False
    
    # 黑名单关键词过滤
    blacklist = config.get('blacklist_keywords', [])
    text = title + ' ' + (summary or '')
    text_lower = text.lower()
    
    for keyword in blacklist:
        if keyword.lower() in text_lower:
            return False
    
    # 标题党特征过滤（放宽）
    clickbait_patterns = [
        r'震惊 [！!]',
        r'重磅 [！!]',
        r'速看',
        r'删前速看',
        r'不转不是',
    ]
    
    for pattern in clickbait_patterns:
        if re.search(pattern, title, re.IGNORECASE):
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
    
    # 放宽匹配阈值：只要匹配 1 个词就算通过
    if matches >= 1:
        return 0.5 + (matches / len(keywords)) * 0.5
    
    return matches / len(keywords) if keywords else 0

def generate_summary(title, summary, max_length=100):
    """
    生成简短摘要
    优先用文章摘要，没有则从标题生成
    """
    if summary:
        # 清理 HTML 标签
        clean_summary = re.sub(r'<[^>]+>', '', summary)
        clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()
        
        # 清理作者信息（36 氪等来源的"作者丨xxx 编辑丨xxx"）
        clean_summary = re.sub(r'作者 [丨|].*?编辑 [丨|].*?\s*', '', clean_summary)
        clean_summary = re.sub(r'作者 [丨|].*?\s*', '', clean_summary)
        
        # 截取
        if len(clean_summary) > max_length:
            return clean_summary[:max_length-3] + '...'
        return clean_summary if clean_summary else f"📰 {title}"
    
    # 没有摘要时，简单描述
    return f"📰 {title[:60]}..." if len(title) > 60 else f"📰 {title}"

def fetch_feeds(feeds_config):
    """
    抓取所有 RSS 源，带筛选和评分
    """
    articles = []
    settings = feeds_config.get('settings', {})
    total_fetched = 0
    category_stats = {}  # 统计每类抓取数量
    
    for feed_config in feeds_config['feeds']:
        try:
            print(f"📰 抓取：{feed_config['name']}")
            feed = feedparser.parse(feed_config['url'])
            
            if not feed.entries:
                print(f"  ⚠️ 无内容")
                continue
            
            weight = feed_config.get('weight', 5)
            keywords = feed_config.get('keywords', [])
            category = feed_config['category']
            is_english = feed_config.get('language', 'zh') == 'en'
            
            if category not in category_stats:
                category_stats[category] = {'fetched': 0, 'passed': 0}
            
            for entry in feed.entries[:settings.get('max_items_per_feed', 15)]:
                total_fetched += 1
                category_stats[category]['fetched'] += 1
                
                title = entry.title
                summary = entry.get('summary', '')
                
                # 质量筛选
                if not is_quality_article(title, summary, settings):
                    continue
                
                # 关键词匹配（放宽）
                match_score = match_keywords(title, summary, keywords)
                
                # 翻译英文内容
                if is_english:
                    print(f"  🌐 翻译：{title[:30]}...")
                    title = translate_text(title)
                    summary = translate_text(summary)
                    time.sleep(0.2)  # 避免 API 限流
                
                # 生成摘要
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
                    'score': weight * match_score,  # 综合评分
                }
                articles.append(article)
                category_stats[category]['passed'] += 1
                
        except Exception as e:
            print(f"❌ 抓取失败 {feed_config['name']}: {e}")
    
    # 打印统计
    print("\n📊 分类统计:")
    for cat, stats in category_stats.items():
        print(f"  {cat}: 抓取{stats['fetched']}条 → 通过{stats['passed']}条")
    
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
        final_articles.extend(items[:15])  # 每类最多 15 条
    
    total_passed = sum(len(items) for items in by_category.values())
    print(f"\n✅ 抓取到 {total_fetched} 条原始内容，筛选后 {total_passed} 条优质文章")
    
    return final_articles

def format_message(articles):
    """
    格式化为飞书消息（带摘要 + 翻译）
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
    
    # 统计实际总数
    total_count = sum(len(items) for items in by_category.values())
    
    # 构建消息
    lines = [
        f"📰 **每日新闻摘要** ({datetime.now().strftime('%Y年%m月%d日')})",
        f"共筛选出 **{total_count}** 条优质内容",
        "=" * 50,
        ""
    ]
    
    # 分类顺序
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
            # 序号 + 标题
            lines.append(f"\n**{i:2d}. {item['title']}**")
            # 来源
            lines.append(f"📍 {item['source']}")
            # 摘要
            lines.append(f"💡 {item['summary']}")
            # 链接
            lines.append(f"🔗 [阅读原文]({item['link']})")
        
        lines.append("")
    
    lines.append("=" * 50)
    lines.append(f"💡 _智能筛选：过滤广告/推广/标题党，英文内容自动翻译_")
    
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
    print(f"   - 每源最多：{config['settings'].get('max_items_per_feed', 15)} 条")
    print(f"   - 每类最多：15 条")
    print(f"   - 最小标题长度：{config['settings'].get('min_title_length', 8)}")
    print(f"   - 黑名单：{', '.join(config['settings'].get('blacklist_keywords', []))}")
    print(f"   - 英文翻译：✅ 开启")
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
