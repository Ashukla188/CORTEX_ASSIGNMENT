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
- Optional: Qdrant running at `http://localhost:6333`
- Optional: OpenAI API key in `.env`

## Setup
1. Create `backend/.env` or root `.env` with:
   ```env
   OPENAI_API_KEY=your_key_here
   OPENAI_CHAT_MODEL=gpt-4o
   QDRANT_URL=http://localhost:6333
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

## Behavior
- OpenAI embeddings are tried first when a key is present.
- If OpenAI fails, the app falls back to `sentence-transformers`.
- If both fail, the app uses deterministic local fallback vectors.
- Chat stays local-only in this build to avoid OpenAI rate/session limits.

## Notes
- If you change `.env`, restart the backend.
- If embeddings change mode, Qdrant adjusts to the active vector size.
- Keep secrets out of git.

---

## Assignment Questions

**What does your system do, and what are the two or three most important architecture decisions you made?**

The system ingests raw social data exports from LinkedIn, Twitter/X, and Instagram, parses only the content that represents the person's own words, embeds it into a Qdrant vector store, and exposes a chat interface where any question is answered with grounded, cited source chunks. The three most important decisions were: content-aware chunking (short-form posts like tweets are kept atomic as one chunk, long-form articles split on paragraph boundaries, so embeddings always capture complete thoughts rather than arbitrary text fragments); deterministic deduplication using native platform IDs with an MD5 fallback (Qdrant's upsert operation handles re-uploads idempotently with zero extra queries); and a three-tier embedding strategy (OpenAI first for quality, sentence-transformers as a free local fallback with real semantic meaning, and a hash-based last resort) so the system stays functional without any API dependency.

**Where is the bottleneck at 10x data volume? What breaks first?**

At 10x volume the first thing that breaks is the embedding step. Currently all chunks from a single file are embedded in one asyncio.gather call — at 10x that means thousands of concurrent batch requests hitting the OpenAI API simultaneously, which will saturate rate limits and cause cascading 429 errors. The sentence-transformers fallback avoids API limits but becomes a CPU bottleneck since it runs synchronously in a thread executor with no batching parallelism. The second thing that strains is the single Qdrant collection with no payload indexing — cosine search across hundreds of thousands of unindexed vectors degrades linearly. The fix is a proper async queue with backpressure for embedding batches, and adding Qdrant payload indexes on `platform` and `created_at` to enable filtered search.

**What did you consciously cut to stay in the 4 to 6 hour window, and what would you build next?**

I cut user authentication (there is no concept of per-user data isolation), streaming responses (answers are returned as a single payload rather than token-by-token), LinkedIn article HTML parsing (rich HTML content is skipped, only plain CSV fields are extracted), and metadata filtering at query time (you cannot yet ask "what did they post on LinkedIn in 2024" — all platforms are searched together). I also cut a proper production deployment in favour of a local Docker setup. The first things I would build next are: per-user Qdrant collections so multiple people can use the system without data bleed, SSE streaming from FastAPI so answers appear progressively, and metadata filters on the search endpoint so queries can be scoped by platform or date range.

**If you had to make this architecture 10x better — not iterate on it, but rethink it — what would you change and why?**

The fundamental rethink would be to decouple ingestion from the request cycle entirely. Right now a file upload blocks an HTTP request while parsing, embedding, and upserting all happen synchronously — that is fine for a demo but wrong at scale. A production-grade version would drop uploaded files into object storage (S3), publish a job to a queue (SQS or Redis Streams), and have a separate worker pool consume those jobs asynchronously with retries and dead-letter handling. The API would return immediately with a job ID and the frontend would poll or subscribe via WebSocket for completion. On the retrieval side I would replace single-vector cosine search with a hybrid retrieval approach — dense vector search combined with sparse BM25 keyword matching — because social content is short and keyword-heavy, and pure dense retrieval misses exact-match queries that sparse search handles trivially. Finally I would add a re-ranking step (a cross-encoder model) between retrieval and generation so the top-5 chunks passed to the LLM are reordered by true relevance rather than raw cosine score, which meaningfully improves answer quality without changing anything else in the stack.