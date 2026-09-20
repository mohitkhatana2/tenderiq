import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from dotenv import load_dotenv
from .database import Base, TenderDocument, engine
from sqlalchemy.orm import Session

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
app = FastAPI(title="TenderIQ API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def create_schema():
    """Creates the local schema; production deployments should use migrations."""
    Base.metadata.create_all(engine)

TENDERS = [
    {"id": "TEN-2026-0184", "title": "Annual GPU Maintenance & Overhaul Services", "organization": "Airports Authority of India", "location": "New Delhi", "deadline": "28 Sep 2026", "value": "₹4.8 Cr", "category": "MRO", "match": 96, "status": "Open", "tags": ["GPU", "Maintenance", "Aviation"]},
    {"id": "TEN-2026-0179", "title": "Procurement of Ground Support Equipment", "organization": "Air India Engineering Services", "location": "Mumbai", "deadline": "02 Oct 2026", "value": "₹12.6 Cr", "category": "Equipment", "match": 92, "status": "Open", "tags": ["GSE", "Aircraft", "Equipment"]},
    {"id": "TEN-2026-0166", "title": "Aircraft Component Repair and Maintenance", "organization": "Hindustan Aeronautics Limited", "location": "Bengaluru", "deadline": "05 Oct 2026", "value": "₹8.2 Cr", "category": "MRO", "match": 88, "status": "Open", "tags": ["Aircraft", "MRO", "Repair"]},
    {"id": "TEN-2026-0148", "title": "Supply and Maintenance of Airfield Lighting", "organization": "Delhi International Airport", "location": "New Delhi", "deadline": "19 Sep 2026", "value": "₹3.1 Cr", "category": "Infrastructure", "match": 71, "status": "Closing soon", "tags": ["Airfield", "Maintenance"]},
]

class Question(BaseModel):
    question: str
    tender_id: str | None = None

def extract_text(path: Path) -> str:
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    except Exception as exc:
        raise HTTPException(422, f"Could not read PDF: {exc}")

def heuristic_analysis(text: str, filename: str) -> dict[str, Any]:
    clean = re.sub(r"\s+", " ", text).strip()
    def grab(pattern: str, fallback: str):
        match = re.search(pattern, clean, re.I)
        return match.group(1).strip(" .:;") if match else fallback
    deadline = grab(r"(?:deadline|due date|last date)[^A-Za-z0-9]{0,20}([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", "Not found — review source")
    value = grab(r"(?:estimated value|tender value|contract value)[^₹$A-Za-z0-9]{0,20}([₹$]?[\d,.]+\s*(?:crore|cr|lakh|million)?)", "Not disclosed")
    return {
        "source": "Heuristic extraction (add OPENAI_API_KEY for AI analysis)",
        "title": grab(r"(?:tender title|name of work|subject)\s*[:\-]\s*([^\n]{8,150})", Path(filename).stem.replace("_", " ").title()),
        "organization": grab(r"(?:issued by|organization|authority)\s*[:\-]\s*([^\n]{4,100})", "Not found — review source"),
        "deadline": deadline, "estimated_value": value,
        "summary": (clean[:420] + "…") if len(clean) > 420 else clean or "No extractable text was found in this document.",
        "eligibility": ["Review turnover and prior-experience clauses in the source PDF.", "Validate statutory registrations and certifications."],
        "technical_requirements": ["Review technical specification and scope-of-work sections.", "Confirm capability, staffing, and service-level coverage."],
        "important_dates": [{"label": "Bid submission deadline", "date": deadline}],
        "required_documents": ["Technical proposal", "Financial proposal", "Company registrations", "Past-performance evidence"],
        "risks": ["Source document requires manual validation for commercial terms.", "Confirm clarification and submission timelines before bidding."],
        "text_preview": clean[:2000],
    }

async def ai_analysis(text: str, filename: str) -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return heuristic_analysis(text, filename)
    schema = {"type":"object","properties":{"title":{"type":"string"},"organization":{"type":"string"},"deadline":{"type":"string"},"estimated_value":{"type":"string"},"summary":{"type":"string"},"eligibility":{"type":"array","items":{"type":"string"}},"technical_requirements":{"type":"array","items":{"type":"string"}},"important_dates":{"type":"array","items":{"type":"object","properties":{"label":{"type":"string"},"date":{"type":"string"}},"required":["label","date"],"additionalProperties":False}},"required_documents":{"type":"array","items":{"type":"string"}},"risks":{"type":"array","items":{"type":"string"}}},"required":["title","organization","deadline","estimated_value","summary","eligibility","technical_requirements","important_dates","required_documents","risks"],"additionalProperties":False}
    prompt = f"Extract the tender details from this PDF. Be precise; use 'Not stated' when absent. PDF: {filename}\n\n{text[:28000]}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {key}"}, json={"model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), "input": prompt, "text": {"format": {"type": "json_schema", "name":"tender_analysis", "schema":schema, "strict":True}}})
        response.raise_for_status()
        result = response.json()
    raw = result.get("output_text", "{}")
    data = json.loads(raw)
    data["source"] = "AI extraction"
    data["text_preview"] = text[:2000]
    return data

@app.get("/health")
def health(): return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/tenders")
def search_tenders(q: str = ""):
    terms = q.lower().split()
    results = [t for t in TENDERS if not terms or any(term in (t["title"] + " " + t["organization"] + " " + " ".join(t["tags"])).lower() for term in terms)]
    return {"items": results, "total": len(results)}

@app.post("/documents/analyze")
async def analyze_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF document.")
    storage = Path("uploads"); storage.mkdir(exist_ok=True)
    path = storage / f"{datetime.now().timestamp()}-{file.filename}"
    path.write_bytes(await file.read())
    text = extract_text(path)
    analysis = await ai_analysis(text, file.filename)
    with Session(engine) as session:
        session.add(TenderDocument(filename=file.filename, extracted_text=text, analysis_json=analysis))
        session.commit()
    return analysis

@app.post("/ask")
async def ask(question: Question):
    return {"answer": "This RAG endpoint is ready to connect to your chunk store. In production, retrieve the most relevant tender chunks by embedding similarity, then answer only from those sources.", "sources": [question.tender_id] if question.tender_id else []}
