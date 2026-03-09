#!/usr/bin/env python3
"""
测试飞书 Webhook 是否有效
用法：python test_webhook.py
"""

import requests
import os

# 你的 Webhook
WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/0332b1be-8cb5-4215-8471-718e4c3556f2"

# 测试消息
message = """
🧪 **Webhook 测试消息**

这是一条测试消息，用于验证飞书推送是否正常工作。

如果收到这条消息，说明：
✅ Webhook 配置正确
✅ 网络连接正常
✅ 飞书机器人可用

时间：2026-03-09
"""

payload = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🧪 Webhook 测试"
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

print("🔍 测试飞书 Webhook...")
print(f"Webhook: {WEBHOOK[:50]}...")
print(f"消息内容：{message[:100]}...")
print("-" * 50)

try:
    response = requests.post(WEBHOOK, json=payload, timeout=30)
    
    print(f"响应状态码：{response.status_code}")
    print(f"响应内容：{response.text}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get('StatusCode') == 0 or result.get('code') == 0:
            print("\n✅ 测试成功！飞书推送正常工作")
        else:
            print(f"\n⚠️ 飞书返回错误：{result}")
    else:
        print(f"\n❌ 推送失败，状态码：{response.status_code}")
        
except Exception as e:
    print(f"\n❌ 请求异常：{e}")
