from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()

RED_FLAG_PHRASES = ["going concern", "material weakness", "guidance withdrawn", "restatement"]
HEADERS = {"User-Agent": "AlphaAgent research@alphaagent.dev"}


@router.get("/sec_filings")
def get_sec_filings(ticker: str):
    try:
        cik = _get_cik(ticker)
        if not cik:
            raise HTTPException(status_code=404, detail=f"CIK not found for {ticker}")

        filings = _get_recent_filings(cik)
        last_10k = next((f for f in filings if f["form"] == "10-K"), None)
        last_10q = next((f for f in filings if f["form"] == "10-Q"), None)
        form4_count = sum(1 for f in filings if f["form"] == "4")

        red_flags = []
        if last_10k:
            red_flags = _scan_red_flags(cik, last_10k["accessionNumber"])

        return {
            "score": _score(red_flags, form4_count),
            "signals": _signals(red_flags, form4_count, last_10k, last_10q),
            "data": {
                "last_10k_date": last_10k["filingDate"] if last_10k else None,
                "last_10q_date": last_10q["filingDate"] if last_10q else None,
                "red_flags": red_flags,
                "form4_count": form4_count,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_cik(ticker: str) -> str | None:
    data = httpx.get(
        "https://www.sec.gov/files/company_tickers.json",
        timeout=10,
        headers=HEADERS,
    ).json()
    for _, co in data.items():
        if not isinstance(co, dict):
            continue
        if co.get("ticker", "").upper() == ticker.upper():
            return str(co["cik_str"]).zfill(10)
    return None


def _get_recent_filings(cik: str) -> list[dict]:
    data = httpx.get(
        f"https://data.sec.gov/submissions/CIK{cik}.json",
        timeout=10,
        headers=HEADERS,
    ).json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])
    return [
        {"form": f, "filingDate": d, "accessionNumber": a}
        for f, d, a in zip(forms, dates, accs)
        if f in ("10-K", "10-Q", "4")
    ][:20]


def _scan_red_flags(cik: str, accession: str) -> list[str]:
    try:
        acc_clean = accession.replace("-", "")
        cik_int = int(cik)

        # Fetch the filing index to find the primary document
        index_url = f"https://data.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/index.json"
        index_data = httpx.get(index_url, timeout=15, headers=HEADERS).json()
        documents = index_data.get("directory", {}).get("item", [])

        # Find the primary 10-K document (first .htm or .txt that isn't the index itself)
        doc_name = None
        for doc in documents:
            name = doc.get("name", "")
            if name.endswith((".htm", ".txt")) and "index" not in name.lower():
                doc_name = name
                break

        if not doc_name:
            return []

        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{doc_name}"
        text = httpx.get(doc_url, timeout=20, headers=HEADERS).text.lower()
        return [phrase for phrase in RED_FLAG_PHRASES if phrase in text]
    except Exception:
        return []


def _score(red_flags: list, form4_count: int) -> float:
    score = 7.0
    score -= len(red_flags) * 2.0
    if form4_count > 5:
        score += 0.5
    return round(max(0.0, min(10.0, score)), 2)


def _signals(red_flags, form4_count, last_10k, last_10q) -> list[str]:
    out = []
    if red_flags:
        for flag in red_flags:
            out.append(f"Red flag: '{flag}'")
    else:
        out.append("No red flags in recent filings")
    if last_10k:
        out.append(f"Most recent 10-K: {last_10k['filingDate']}")
    if last_10q:
        out.append(f"Most recent 10-Q: {last_10q['filingDate']}")
    if form4_count > 3:
        out.append(f"Active insider transactions: {form4_count} Form 4s recently")
    return out
