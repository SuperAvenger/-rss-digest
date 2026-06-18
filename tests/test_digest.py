from scripts.fetch_and_push import format_message, is_quality_article, match_keywords, push_to_feishu


def test_quality_filter_and_keyword_score():
    config = {"min_title_length": 8, "blacklist_keywords": ["广告"]}
    assert is_quality_article("这是一个足够长的标题", "内容", config)
    assert not is_quality_article("短", "内容", config)
    assert not is_quality_article("这是一个广告推广标题", "内容", config)
    assert match_keywords("OpenAI 发布模型", "", ["OpenAI", "Anthropic"]) == 0.75


def test_format_message_groups_articles():
    message = format_message(
        [
            {
                "category": "AI",
                "title": "Example",
                "source": "Source",
                "summary": "中文摘要",
                "link": "https://example.com/article",
            }
        ]
    )
    assert "AI (1条)" in message
    assert "https://example.com/article" in message


def test_push_to_feishu_checks_business_code(monkeypatch):
    class Response:
        status_code = 200
        text = '{"code": 19001}'

        def json(self):
            return {"code": 19001}

    monkeypatch.setenv("FEISHU_WEBHOOK", "https://example.com/hook")
    monkeypatch.setattr("scripts.fetch_and_push.requests.post", lambda *args, **kwargs: Response())

    assert push_to_feishu("message") is False
