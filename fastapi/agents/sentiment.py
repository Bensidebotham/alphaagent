import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()


@router.get("/sentiment")
def get_sentiment(ticker: str):
    finnhub_key = os.environ.get("FINNHUB_API_KEY", "")
    try:
        sent = httpx.get(
            "https://finnhub.io/api/v1/news-sentiment",
            params={"symbol": ticker, "token": finnhub_key},
            timeout=10,
        ).json()

        if not isinstance(sent, dict):
            raise HTTPException(status_code=503, detail="Finnhub sentiment API returned unexpected response")

        to_d = datetime.now().strftime("%Y-%m-%d")
        from_d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        news = httpx.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": from_d, "to": to_d, "token": finnhub_key},
            timeout=10,
        ).json()

        raw_bullish = sent.get("sentiment", {}).get("bullishPercent", 0.5)
        raw_bullish = min(1.0, max(0.0, raw_bullish))
        bullish_pct = raw_bullish * 100
        bearish_pct = 100 - bullish_pct
        article_count = sent.get("buzz", {}).get("articlesInLastWeek", 0)
        finnhub_score = bullish_pct / 100
        score = round(finnhub_score * 10, 2)

        headlines = [
            {"headline": a.get("headline", ""), "datetime": a.get("datetime", 0)}
            for a in (news[:5] if isinstance(news, list) else [])
        ]

        signals = []
        if bullish_pct > 65:
            signals.append(f"Strongly bullish: {bullish_pct:.0f}% positive news")
        elif bullish_pct > 50:
            signals.append(f"Mildly bullish: {bullish_pct:.0f}% positive")
        elif bearish_pct > 65:
            signals.append(f"Strongly bearish: {bearish_pct:.0f}% negative news")
        else:
            signals.append(f"Mixed sentiment: {bullish_pct:.0f}% bullish")
        if article_count > 20:
            signals.append(f"High media buzz: {article_count} articles this week")

        return {
            "score": score,
            "signals": signals,
            "data": {
                "article_count": article_count,
                "bullish_pct": round(bullish_pct, 1),
                "bearish_pct": round(bearish_pct, 1),
                "finnhub_score": round(finnhub_score, 3),
                "top_headlines": headlines,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
