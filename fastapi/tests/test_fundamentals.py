import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)


def _mock_info(pe=18.0, margin=0.25, dte=45.0, rev_growth=0.20, eps_growth=0.15):
    return {
        "trailingPE": pe,
        "profitMargins": margin,
        "debtToEquity": dte,
        "revenueGrowth": rev_growth,
        "earningsGrowth": eps_growth,
    }


@patch("agents.fundamentals.yf.Ticker")
def test_fundamentals_returns_score_and_data(mock_ticker):
    mock_ticker.return_value.info = _mock_info()
    resp = client.get("/agents/fundamentals?ticker=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert "signals" in body
    assert "data" in body
    assert 0 <= body["score"] <= 10


@patch("agents.fundamentals.yf.Ticker")
def test_high_quality_company_scores_above_7(mock_ticker):
    mock_ticker.return_value.info = _mock_info(pe=18, margin=0.30, dte=30, rev_growth=0.25, eps_growth=0.20)
    resp = client.get("/agents/fundamentals?ticker=AAPL")
    assert resp.json()["score"] > 7


@patch("agents.fundamentals.yf.Ticker")
def test_negative_margin_scores_below_5(mock_ticker):
    mock_ticker.return_value.info = _mock_info(pe=-1, margin=-0.10, dte=300, rev_growth=-0.05, eps_growth=-0.20)
    resp = client.get("/agents/fundamentals?ticker=BAD")
    assert resp.json()["score"] < 5


@patch("agents.fundamentals.yf.Ticker")
def test_signals_list_is_populated(mock_ticker):
    mock_ticker.return_value.info = _mock_info(margin=0.30, rev_growth=0.25, dte=300)
    resp = client.get("/agents/fundamentals?ticker=AAPL")
    signals = resp.json()["signals"]
    assert isinstance(signals, list)
    assert len(signals) > 0
