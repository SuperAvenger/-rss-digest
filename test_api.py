#!/usr/bin/env python3
"""
测试 API 是否正常工作
"""

import requests
import json

# OpenRouter 配置
OPENROUTER_API_KEY = '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'
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "stepfun/step-3.5-flash:free"

# Gemini 配置
GEMINI_API_KEY = 'AIzaSyBPBoLcA_yC_S1udnDrzRCvKIISHsO4UTk'
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview:generateContent"

test_title = "OpenAI releases GPT-5.4"
test_content = "OpenAI today announced GPT-5.4, the latest version of its flagship AI model. The new model features improved reasoning capabilities, better coding skills, and a 1 million token context window."

print("=" * 70)
print("🧪 API 测试")
print("=" * 70)

# 测试 1：stepfun
print("\n1️⃣ 测试 stepfun (OpenRouter)...")
print(f"   模型：{OPENROUTER_MODEL}")

stepfun_prompt = f"""你是一个专业的新闻编辑。请将以下英文新闻翻译成中文并总结：

【英文原文】
标题：{test_title}
内容：{test_content}

【要求】
1. 必须翻译成中文
2. 用 60-100 字概括核心内容
3. 直接输出翻译结果

【中文翻译】"""

try:
    response = requests.post(
        OPENROUTER_ENDPOINT,
        headers={
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/SuperAvenger/rss-digest',
            'X-Title': 'RSS Test'
        },
        json={
            'model': OPENROUTER_MODEL,
            'messages': [
                {'role': 'system', 'content': '你是一个专业的中文新闻翻译。用户输入英文时，你必须用中文回复。'},
                {'role': 'user', 'content': stepfun_prompt}
            ],
            'max_tokens': 200,
            'temperature': 0.3
        },
        timeout=40
    )
    
    print(f"   状态码：{response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ 请求成功")
        
        if 'choices' in result and result['choices']:
            summary = result['choices'][0]['message']['content'].strip()
            print(f"\n   翻译结果:")
            print(f"   {summary}")
            
            # 检查是否中文
            import re
            if re.search(r'[\u4e00-\u9fff]', summary):
                print(f"\n   ✅ 翻译成功（包含中文）")
            else:
                print(f"\n   ❌ 翻译失败（返回英文）")
        else:
            print(f"   ❌ 响应格式错误：{result}")
    else:
        print(f"   ❌ API 错误：{response.status_code}")
        print(f"   响应：{response.text[:200]}")
        
except Exception as e:
    print(f"   ❌ 异常：{e}")

# 测试 2：Gemini
print("\n" + "=" * 70)
print("\n2️⃣ 测试 Google Gemini...")
print(f"   模型：gemini-2.0-flash-preview")

gemini_prompt = f"""Translate this English news to Chinese and summarize in 60-100 Chinese characters:

Title: {test_title}
Content: {test_content}

Output ONLY the Chinese summary, no other text:"""

try:
    response = requests.post(
        f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
        headers={'Content-Type': 'application/json'},
        json={
            "contents": [{
                "parts": [{
                    "text": gemini_prompt
                }]
            }],
            "generationConfig": {
                "maxOutputTokens": 200,
                "temperature": 0.3
            }
        },
        timeout=30
    )
    
    print(f"   状态码：{response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ 请求成功")
        
        if 'candidates' in result and result['candidates']:
            summary = result['candidates'][0]['content']['parts'][0]['text'].strip()
            print(f"\n   翻译结果:")
            print(f"   {summary}")
            
            # 检查是否中文
            import re
            if re.search(r'[\u4e00-\u9fff]', summary):
                print(f"\n   ✅ 翻译成功（包含中文）")
            else:
                print(f"\n   ❌ 翻译失败（返回英文）")
        else:
            print(f"   ❌ 响应格式错误：{result}")
    else:
        print(f"   ❌ API 错误：{response.status_code}")
        print(f"   响应：{response.text[:200]}")
        
except Exception as e:
    print(f"   ❌ 异常：{e}")

print("\n" + "=" * 70)
print("📋 测试完成")
print("=" * 70)
