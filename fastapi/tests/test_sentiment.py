import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

MOCK_SENTIMENT = {
    "sentiment": {"bullishPercent": 0.75, "bearishPercent": 0.25},
    "buzz": {"articlesInLastWeek": 25},
}

MOCK_NEWS = [
    {"headline": "Apple beats earnings", "datetime": 1700000000},
    {"headline": "iPhone sales strong", "datetime": 1700000001},
]


@patch("agents.sentiment.httpx.get")
def test_sentiment_returns_score_and_data(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "news-sentiment" in url:
            m.json.return_value = MOCK_SENTIMENT
        else:
            m.json.return_value = MOCK_NEWS
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sentiment?ticker=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert 0 <= body["score"] <= 10
    assert "bullish_pct" in body["data"]


@patch("agents.sentiment.httpx.get")
def test_bullish_sentiment_scores_above_6(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "news-sentiment" in url:
            m.json.return_value = {"sentiment": {"bullishPercent": 0.80}, "buzz": {"articlesInLastWeek": 10}}
        else:
            m.json.return_value = []
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sentiment?ticker=AAPL")
    assert resp.json()["score"] > 6


@patch("agents.sentiment.httpx.get")
def test_top_headlines_in_data(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "news-sentiment" in url:
            m.json.return_value = MOCK_SENTIMENT
        else:
            m.json.return_value = MOCK_NEWS
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sentiment?ticker=AAPL")
    assert isinstance(resp.json()["data"]["top_headlines"], list)
