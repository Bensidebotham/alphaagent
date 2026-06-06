from fastapi import APIRouter, HTTPException
import yfinance as yf
import pandas as pd
import numpy as np

router = APIRouter()


@router.get("/technical")
def get_technical(ticker: str):
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No price history for {ticker}")

        closes = hist["Close"]
        rsi = _rsi(closes, 14)
        ma_50 = float(closes.rolling(50).mean().iloc[-1])
        ma_200 = float(closes.rolling(200).mean().iloc[-1])
        price = float(closes.iloc[-1])
        high_52w = float(hist["High"].max())
        avg_vol_20 = float(hist["Volume"].rolling(20).mean().iloc[-1])
        cur_vol = float(hist["Volume"].iloc[-1])
        vol_ratio = cur_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0
        pct_from_high = ((price - high_52w) / high_52w) * 100

        return {
            "score": _score(rsi, price, ma_50, ma_200),
            "signals": _signals(rsi, price, ma_50, ma_200, vol_ratio),
            "data": {
                "rsi": round(rsi, 2),
                "ma_50": round(ma_50, 2),
                "ma_200": round(ma_200, 2),
                "current_price": round(price, 2),
                "volume_ratio": round(vol_ratio, 2),
                "price_vs_52w_high_pct": round(pct_from_high, 2),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return float((100 - (100 / (1 + rs))).iloc[-1])


def _score(rsi, price, ma50, ma200) -> float:
    score = 5.0
    if 40 <= rsi <= 60:
        score += 1.0
    elif rsi < 30:
        score += 1.5
    elif rsi > 70:
        score -= 1.0
    if price > ma50:
        score += 1.5
    else:
        score -= 0.5
    if ma50 > ma200:
        score += 1.5
    else:
        score -= 1.0
    return round(max(0.0, min(10.0, score)), 2)


def _signals(rsi, price, ma50, ma200, vol_ratio) -> list[str]:
    out = [f"RSI: {rsi:.1f}"]
    if rsi > 70:
        out.append("Overbought (RSI > 70)")
    elif rsi < 30:
        out.append("Oversold (RSI < 30)")
    out.append("Golden cross (50MA > 200MA)" if ma50 > ma200 else "Death cross (50MA < 200MA)")
    out.append("Price above 50-day MA" if price > ma50 else "Price below 50-day MA")
    if vol_ratio > 1.5:
        out.append(f"High volume: {vol_ratio:.1f}× average")
    return out
