from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline.embedder import Embedder
from pipeline.ingestor import Ingestor
from rag.chat import RagChat
from vector_store.qdrant_client import QdrantStore

import os
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=True)

api_key = os.getenv("OPENAI_API_KEY", "").strip()
print(f"KEY LOADED: {'yes' if api_key else 'no'} (len={len(api_key)})")


def _load_cors_origins() -> list[str]:
    local_origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://cortex-frontend-u7ma.onrender.com",
    }
    env_origins = {
        origin.strip().rstrip("/")
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    }
    return sorted(local_origins | env_origins)


def _load_cors_origin_regex() -> str | None:
    regex = os.getenv("CORS_ORIGIN_REGEX", "").strip()
    if regex:
        return regex
    return r"^https://.*\.onrender\.com$"


class ChatRequest(BaseModel):
    question: str
    top_k: int = 5


def create_app() -> FastAPI:
    app = FastAPI(title="Cortex Assignment API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_load_cors_origins(),
        allow_origin_regex=_load_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # These objects are shared across requests so the app uses one embedding path and one vector store.
    # If startup fails here, check package installs, QDRANT_URL, and OPENAI_API_KEY.
    print("[startup] initializing shared services")
    print(f"[startup] cors_origins={_load_cors_origins()}")
    print(f"[startup] cors_origin_regex={_load_cors_origin_regex()!r}")
    embedder = Embedder()
    store = QdrantStore()
    ingestor = Ingestor(embedder, store)
    rag = RagChat(embedder, store)
    print(f"[startup] vector_store_mode={'qdrant' if store._client is not None else 'memory'}")

    app.state.embedder = embedder
    app.state.store = store
    app.state.ingestor = ingestor
    app.state.rag = rag

    @app.get("/health")
    async def health():
        print("[health] health check requested")
        return {
            "ok": True,
            "vector_store": "qdrant" if store._client is not None else "memory",
            "store_healthy": store.health(),
        }

    @app.post("/ingest")
    async def ingest(
        files: List[UploadFile] = File(...),
        source_type: Optional[str] = Form(default=None),
    ):
        # Each uploaded file is parsed independently so one bad export does not block the rest.
        print(f"[ingest] received {len(files)} file(s), source_type={source_type!r}")
        # Each new ingest request replaces the previous knowledge base so answers stay scoped to the latest upload batch.
        store.clear()
        results = []
        for upload in files:
            print(f"[ingest] processing file={upload.filename!r}")
            try:
                result = await ingestor.ingest_file(upload, source_type=source_type)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            print(
                f"[ingest] finished file={upload.filename!r} records={result['records']} "
                f"chunks={result['chunks']} inserted={result['inserted']}"
            )
            results.append({"filename": upload.filename, **result})
        return {"results": results}

    @app.post("/chat")
    async def chat(request: ChatRequest):
        # This endpoint depends on both embedding and retrieval. If answers look empty, test /health first.
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="question is required")
        print(f"[chat] question={request.question.strip()!r} top_k={request.top_k}")
        answer = await rag.answer(request.question.strip(), top_k=request.top_k)
        print(f"[chat] returned {len(answer.sources)} source(s)")
        return {"answer": answer.answer, "sources": answer.sources}

    @app.get("/")
    async def root():
        return {"service": "cortex-assignment-api", "status": "ready"}

    return app


app = create_app()
