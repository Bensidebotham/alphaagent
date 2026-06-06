from fastapi import APIRouter, HTTPException
import yfinance as yf

router = APIRouter()


@router.get("/fundamentals")
def get_fundamentals(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        pe = info.get("trailingPE")
        margin = info.get("profitMargins")
        dte = info.get("debtToEquity")
        rev_growth = info.get("revenueGrowth")
        eps_growth = info.get("earningsGrowth")

        return {
            "score": _score(pe, margin, dte, rev_growth, eps_growth),
            "signals": _signals(pe, margin, dte, rev_growth, eps_growth),
            "data": {
                "pe_ratio": pe,
                "profit_margin_pct": round(margin * 100, 2) if margin is not None else None,
                "debt_to_equity": dte,
                "revenue_growth_pct": round(rev_growth * 100, 2) if rev_growth is not None else None,
                "eps_growth_pct": round(eps_growth * 100, 2) if eps_growth is not None else None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _score(pe, margin, dte, rev_growth, eps_growth) -> float:
    score = 5.0
    if margin is not None:
        if margin > 0.20:
            score += 1.5
        elif margin > 0.10:
            score += 0.75
        elif margin < 0:
            score -= 2.0
    if rev_growth is not None:
        if rev_growth > 0.20:
            score += 1.5
        elif rev_growth > 0.05:
            score += 0.75
        elif rev_growth < 0:
            score -= 1.0
    if dte is not None:
        if dte < 50:
            score += 0.5
        elif dte > 200:
            score -= 1.5
    if pe is not None:
        if pe < 0:
            score -= 1.0
        elif pe < 15:
            score += 0.5
        elif pe > 50:
            score -= 0.5
    return round(max(0.0, min(10.0, score)), 2)


def _signals(pe, margin, dte, rev_growth, eps_growth) -> list[str]:
    out = []
    if margin is not None and margin > 0.20:
        out.append(f"Strong profit margin: {margin*100:.1f}%")
    if margin is not None and margin < 0:
        out.append(f"Negative margin: {margin*100:.1f}%")
    if rev_growth is not None and rev_growth > 0.15:
        out.append(f"Strong revenue growth: {rev_growth*100:.1f}% YoY")
    if rev_growth is not None and rev_growth < 0:
        out.append(f"Revenue declining: {rev_growth*100:.1f}% YoY")
    if dte is not None and dte > 200:
        out.append(f"High leverage: D/E {dte:.0f}%")
    if pe is not None and pe < 0:
        out.append("Negative earnings (P/E N/A)")
    if not out:
        out.append("Fundamentals within normal range")
    return out
