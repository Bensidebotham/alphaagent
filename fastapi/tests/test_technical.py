import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)


def _make_history(n=250, trend="up"):
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    if trend == "up":
        closes = np.linspace(100, 180, n) + np.random.normal(0, 2, n)
    else:
        closes = np.linspace(180, 100, n) + np.random.normal(0, 2, n)
    volumes = np.random.randint(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame({"Close": closes, "High": closes * 1.01, "Volume": volumes}, index=dates)


@patch("agents.technical.yf.Ticker")
def test_technical_returns_score_and_data(mock_ticker):
    mock_ticker.return_value.history.return_value = _make_history()
    resp = client.get("/agents/technical?ticker=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert "data" in body
    assert "rsi" in body["data"]
    assert 0 <= body["score"] <= 10


@patch("agents.technical.yf.Ticker")
def test_uptrend_scores_higher_than_downtrend(mock_ticker):
    mock_ticker.return_value.history.return_value = _make_history(trend="up")
    up_score = client.get("/agents/technical?ticker=AAPL").json()["score"]

    mock_ticker.return_value.history.return_value = _make_history(trend="down")
    down_score = client.get("/agents/technical?ticker=AAPL").json()["score"]

    assert up_score > down_score


@patch("agents.technical.yf.Ticker")
def test_empty_history_returns_404(mock_ticker):
    mock_ticker.return_value.history.return_value = pd.DataFrame()
    resp = client.get("/agents/technical?ticker=FAKE")
    assert resp.status_code == 404
