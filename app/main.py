from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .db import init_db
from .ingest import ingest_pdf_folder
from .search import search
from .model import ModelClient

logging.basicConfig(level=logging.INFO)

PDF_FOLDER = Path("data/pdfs")

app = FastAPI(title="PDF Demo Indexer")
model = ModelClient()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


class SearchRequest(BaseModel):
    query: str
    k: int = 5
    use_model: bool = False


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ingest")
def ingest():
    try:
        stats = ingest_pdf_folder(PDF_FOLDER)
        return {"folder": str(PDF_FOLDER.resolve()), "stats": stats}
    except Exception as e:
        logging.error(f"Ingest failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")

@app.post("/search")
def do_search(req: SearchRequest):
    try:
        # Input validation
        if not req.query or not req.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        if req.k <= 0 or req.k > 100:
            raise HTTPException(status_code=400, detail="k must be between 1 and 100")

        results = search(req.query, req.k)

        context = "\n\n---\n\n".join(
            [f"Source: {r['path']} (p.{r['page_num']})\n{r['text']}" for r in results[:7]]
        )

        answer = None
        if req.use_model:
            answer = model.answer(req.query, context)

        return {"query": req.query, "answer": answer, "context": context, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
