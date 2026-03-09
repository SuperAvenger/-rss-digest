#!/usr/bin/env python3
"""
RSS 每日摘要 - 双模型故障转移
主模型：stepfun/step-3.5-flash:free (OpenRouter)
备用：Google Gemini 2.0 Flash (Google AI Studio)
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

# OpenRouter 配置（主模型）
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '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')
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "stepfun/step-3.5-flash:free"

# Google Gemini 配置（备用模型）
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyBPBoLcA_yC_S1udnDrzRCvKIISHsO4UTk')
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview:generateContent"

# 日志记录
API_LOGS = []

def load_feeds():
    config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def translate_with_gemini(title, content):
    """使用 Google Gemini 翻译"""
    clean_content = re.sub(r'<[^>]+>', '', content)
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()[:600]
    
    prompt = f"""Translate this English news to Chinese and summarize in 60-100 Chinese characters:

Title: {title}
Content: {clean_content}

Output ONLY the Chinese summary, no other text:"""
    
    try:
        response = requests.post(
            f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json={
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "maxOutputTokens": 200,
                    "temperature": 0.3
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                summary = result['candidates'][0]['content']['parts'][0]['text'].strip()
                summary = summary.strip('"\'')
                
                # 验证翻译
                if len(summary) > 20 and re.search(r'[A-Za-z]{10,}', summary):
                    return None  # 翻译失败
                
                return summary[:120] + ('...' if len(summary) > 120 else '')
        
        return None
        
    except Exception as e:
        print(f"  ⚠️ Gemini 失败：{e}")
        return None

def ai_translate_and_summarize(title, content, index=0):
    """AI 翻译 + 总结，带故障转移"""
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
    
    log_entry = {
        'index': index,
        'title': title[:50],
        'content_len': len(clean_content),
        'request_time': datetime.now().isoformat()
    }
    
    # 尝试 1：stepfun (OpenRouter)
    print(f"  🔄 尝试 stepfun...")
    stepfun_result = try_stepfun(title, clean_content, log_entry)
    
    if stepfun_result and not stepfun_result.startswith('['):
        log_entry['model'] = 'stepfun'
        log_entry['success'] = True
        API_LOGS.append(log_entry)
        return stepfun_result
    
    # 尝试 2：Google Gemini（故障转移）
    print(f"  🔄 stepfun 失败，尝试 Gemini...")
    gemini_result = translate_with_gemini(title, clean_content)
    
    if gemini_result:
        log_entry['model'] = 'gemini'
        log_entry['success'] = True
        log_entry['fallback'] = True
        API_LOGS.append(log_entry)
        print(f"  ✅ Gemini 成功")
        return gemini_result
    
    # 都失败了
    log_entry['model'] = 'both_failed'
    log_entry['success'] = False
    API_LOGS.append(log_entry)
    print(f"  ❌ 两个模型都失败")
    return f"[翻译失败] {title[:40]}..."

def try_stepfun(title, clean_content, log_entry):
    """尝试 stepfun 模型"""
    prompt = f"""你是一个专业的新闻编辑。请将以下英文新闻翻译成中文并总结：

【英文原文】
标题：{title}
内容：{clean_content}

【要求】
1. 必须翻译成中文
2. 用 60-100 字概括核心内容
3. 保留关键数据、人名、公司名
4. 输出纯中文，不要保留英文句子
5. 直接输出翻译结果，不要其他说明

【中文翻译】"""
    
    try:
        start_time = time.time()
        
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
                'messages': [
                    {'role': 'system', 'content': '你是一个专业的中文新闻翻译。用户输入英文时，你必须用中文回复。'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 200,
                'temperature': 0.3
            },
            timeout=40
        )
        
        elapsed = time.time() - start_time
        log_entry['stepfun_time_ms'] = int(elapsed * 1000)
        log_entry['stepfun_status'] = response.status_code
        
        if response.status_code == 200:
            result = response.json()
            
            if 'choices' in result and result['choices']:
                summary = result['choices'][0]['message']['content'].strip()
                summary = summary.strip('"\'')
                
                log_entry['stepfun_response'] = summary[:100]
                
                # 验证翻译
                if len(summary) > 20 and re.search(r'[A-Za-z]{10,}', summary):
                    log_entry['stepfun_error'] = '翻译失败 - 返回英文'
                    return f"[翻译失败] {title[:40]}..."
                
                if len(summary) > 120:
                    summary = summary[:117] + '...'
                
                return summary
            
            log_entry['stepfun_error'] = f'响应格式错误：{result}'
            return f"[格式错误] {title[:40]}..."
        
        log_entry['stepfun_error'] = f'HTTP {response.status_code}: {response.text[:100]}'
        print(f"  ❌ stepfun 失败：{response.status_code}")
        return f"[API 错误{response.status_code}] {title[:40]}..."
        
    except requests.exceptions.Timeout:
        log_entry['stepfun_error'] = '请求超时'
        print(f"  ⏱️ stepfun 超时")
        return f"[超时] {title[:40]}..."
    except Exception as e:
        log_entry['stepfun_error'] = str(e)
        print(f"  ❌ stepfun 异常：{e}")
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
    
    print(f"\n🤖 双模型故障转移:")
    print(f"   主模型：{OPENROUTER_MODEL} (OpenRouter)")
    print(f"   备用：Google Gemini 2.0 Flash")
    print(f"   策略：stepfun 失败 → 自动切换 Gemini")
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
                category_stats[category] = {'fetched': 0, 'passed': 0, 'failed': 0, 'stepfun_ok': 0, 'gemini_ok': 0, 'fail': 0}
            
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
                is_english = feed_config.get('language', 'zh') == 'en'
                
                if is_english:
                    print(f"  🌐 [{article_index:2d}] {title[:30]}...")
                else:
                    print(f"  📝 [{article_index:2d}] {title[:30]}...")
                
                brief = ai_translate_and_summarize(title, summary, article_index)
                
                # 统计
                if brief.startswith('[翻译失败]'):
                    category_stats[category]['fail'] += 1
                    print(f"      ❌ {brief[:50]}")
                elif is_english:
                    # 检查是用哪个模型成功的
                    last_log = API_LOGS[-1] if API_LOGS else {}
                    if last_log.get('model') == 'gemini':
                        category_stats[category]['gemini_ok'] += 1
                        print(f"      ✅ (Gemini) {brief[:40]}...")
                    else:
                        category_stats[category]['stepfun_ok'] += 1
                        print(f"      ✅ (stepfun) {brief[:40]}...")
                else:
                    category_stats[category]['stepfun_ok'] += 1
                
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
    
    # 打印统计
    print("\n" + "=" * 70)
    print("📊 分类统计:")
    print("=" * 70)
    for cat, stats in category_stats.items():
        status = "✅" if stats['passed'] > 0 else "❌"
        print(f"{status} {cat}:")
        print(f"   抓取{stats['fetched']}条 → 通过{stats['passed']}条 → 过滤{stats['failed']}条")
        print(f"   stepfun 成功{stats['stepfun_ok']}条 → Gemini 救场{stats['gemini_ok']}条 → 失败{stats['fail']}条")
    
    # API 日志摘要
    print("\n" + "=" * 70)
    print("📝 API 调用统计:")
    print("=" * 70)
    
    stepfun_success = sum(1 for log in API_LOGS if log.get('model') == 'stepfun' and log.get('success'))
    gemini_success = sum(1 for log in API_LOGS if log.get('model') == 'gemini' and log.get('success'))
    both_failed = sum(1 for log in API_LOGS if log.get('model') == 'both_failed')
    
    print(f"总调用：{len(API_LOGS)} 次")
    print(f"stepfun 成功：{stepfun_success} 次")
    print(f"Gemini 救场：{gemini_success} 次 ← 故障转移成功")
    print(f"两个都失败：{both_failed} 次")
    
    if both_failed > 0:
        print(f"\n失败详情:")
        for log in API_LOGS:
            if log.get('model') == 'both_failed':
                print(f"  [{log['index']:2d}] {log['title'][:40]}...")
    
    # 保存日志
    log_file = Path(__file__).parent.parent / 'api_logs.json'
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(API_LOGS, f, ensure_ascii=False, indent=2)
    print(f"\n📄 详细日志：{log_file}")
    
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
    print(f"\n✅ 总计：{total_fetched} 条 → {total_passed} 条")
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
    lines.append(f"💡 _双模型翻译：stepfun → Gemini 故障转移_")
    
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
    except Exception as e:
        print(f"❌ 推送异常：{e}")

def main():
    print("=" * 70)
    print("🚀 RSS 智能摘要 - 双模型故障转移")
    print("=" * 70)
    
    config = load_feeds()
    print(f"📋 {len(config['feeds'])} 个 RSS 源")
    print(f"📊 每源最多：{config['settings'].get('max_items_per_feed', 15)} 条")
    print(f"🤖 主模型：{OPENROUTER_MODEL}")
    print(f"🔄 备用：Google Gemini 2.0 Flash")
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
