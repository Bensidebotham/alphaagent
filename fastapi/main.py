from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agents import fundamentals, technical, sentiment, sec_filings

app = FastAPI(title="AlphaAgent FastAPI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fundamentals.router, prefix="/agents")
app.include_router(technical.router, prefix="/agents")
app.include_router(sentiment.router, prefix="/agents")
app.include_router(sec_filings.router, prefix="/agents")


@app.get("/health")
def health():
    return {"status": "ok"}
