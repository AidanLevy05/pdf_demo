from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from .db import init_db
from .ingest import ingest_pdf_folder
from .search import search
from .model import ModelClient

PDF_FOLDER = Path("data/pdfs")

app = FastAPI(title="PDF Demo Indexer")
model = ModelClient()


class SearchRequest(BaseModel):
    query: str
    k: int = 5
    use_model: bool = False


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ingest")
def ingest():
    stats = ingest_pdf_folder(PDF_FOLDER)
    return {"folder": str(PDF_FOLDER.resolve()), "stats": stats}

@app.post("/search")
def do_search(req: SearchRequest):
    results = search(req.query, req.k)

    context = "\n\n---\n\n".join(
        [f"Source: {r['path']} (p.{r['page_num']})\n{r['text']}" for r in results[:3]]
    )

    answer = None
    if req.use_model:
        answer = model.answer(req.query, context)

    return {"query": req.query, "answer": answer, "context": context, "results": results}
