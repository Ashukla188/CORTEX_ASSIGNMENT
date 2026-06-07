# Cortex Assignment

Compact RAG app that ingests LinkedIn, Twitter/X, and Instagram exports, stores embeddings in Qdrant or local memory, and answers questions from the uploaded content.

## Stack
- Backend: FastAPI + Python
- Vector store: Qdrant, with in-memory fallback
- Embeddings: OpenAI first, `sentence-transformers` fallback, hash fallback last
- Frontend: Vite + React

## Requirements
- Python 3.10+
- Node.js 18+
- `pip`
- `npm`
- Optional: local Qdrant at `http://localhost:6333`
- Optional: OpenAI API key in `.env`

## Setup
1. Use the root `.env` in the project folder:
   ```env
   OPENAI_API_KEY=your_key_here
   OPENAI_CHAT_MODEL=gpt-4o
   QDRANT_URL=your_qdrant_url
   QDRANT_API_KEY=your_qdrant_key
   CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   VITE_API_URL=http://localhost:8000
   ```
2. Install backend deps:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
3. Install frontend deps:
   ```bash
   cd frontend
   npm install
   ```

## Run
- Backend:
  ```bash
  cd backend
  uvicorn main:app --reload --port 8000
  ```
- Frontend:
  ```bash
  cd frontend
  npm run dev
  ```

## Usage
- Pick a source type before upload.
- LinkedIn accepts `.csv` only.
- Twitter/X accepts `.json`.
- Instagram accepts `.json` or `.html`.
- Upload clears the previous dataset, so each ingest replaces the active knowledge base.
- Ask questions in the chat panel after ingestion.

## Deployment
- Backend on Render:
  - Create a Python web service from `render.yaml`.
  - Set `QDRANT_URL` and `QDRANT_API_KEY` to your Qdrant Cloud values.
  - Set `OPENAI_API_KEY` and `OPENAI_CHAT_MODEL` if you use OpenAI embeddings.
  - Set `CORS_ORIGINS` to your Vercel URL, for example `https://your-app.vercel.app`.
- Frontend on Vercel:
  - Set `VITE_API_URL` to your Render backend URL, for example `https://your-api.onrender.com`.
  - Rebuild after changing env vars because Vite bakes them in at build time.

## Behavior
- OpenAI embeddings are tried first when a key is present.
- If OpenAI fails, the app falls back to `sentence-transformers`.
- If both fail, the app uses deterministic local fallback vectors.
- Chat stays local-only in this build to avoid OpenAI rate/session limits.

## Notes
- If you change `.env`, restart the backend and frontend dev server.
- If you change `VITE_API_URL`, redeploy the frontend.
- If embeddings change mode, Qdrant adjusts to the active vector size.
- Keep secrets out of git.
