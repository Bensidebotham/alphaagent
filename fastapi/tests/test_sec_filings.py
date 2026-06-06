import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

MOCK_TICKERS = {
    "0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}
}

MOCK_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q", "4", "4"],
            "filingDate": ["2024-11-01", "2024-08-01", "2024-10-15", "2024-09-15"],
            "accessionNumber": ["0000320193-24-000123", "0000320193-24-000456", "x", "x"],
        }
    }
}


@patch("agents.sec_filings.httpx.get")
def test_sec_returns_score_and_data(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "company_tickers" in url:
            m.json.return_value = MOCK_TICKERS
        elif "submissions" in url:
            m.json.return_value = MOCK_SUBMISSIONS
        elif "index.json" in url:
            m.json.return_value = {
                "directory": {
                    "item": [{"name": "aapl-20241026.htm", "type": "10-K"}]
                }
            }
        else:
            m.text = "Annual report with no issues."
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sec_filings?ticker=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert 0 <= body["score"] <= 10
    assert "last_10k_date" in body["data"]


@patch("agents.sec_filings.httpx.get")
def test_red_flags_lower_score(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "company_tickers" in url:
            m.json.return_value = MOCK_TICKERS
        elif "submissions" in url:
            m.json.return_value = MOCK_SUBMISSIONS
        elif "index.json" in url:
            m.json.return_value = {
                "directory": {
                    "item": [{"name": "aapl-20241026.htm", "type": "10-K"}]
                }
            }
        else:
            m.text = "going concern material weakness guidance withdrawn"
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sec_filings?ticker=AAPL")
    assert resp.json()["score"] < 5


@patch("agents.sec_filings.httpx.get")
def test_unknown_ticker_returns_404(mock_get):
    m = MagicMock()
    m.json.return_value = {}
    mock_get.return_value = m

    resp = client.get("/agents/sec_filings?ticker=ZZZZ")
    assert resp.status_code == 404
