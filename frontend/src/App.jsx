import { useMemo, useState } from "react";
import FileUpload from "./components/FileUpload";
import ChatWindow from "./components/ChatWindow";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export default function App() {
  const [ingestResults, setIngestResults] = useState([]);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Upload source exports, then ask what the person thinks about a topic.",
    },
  ]);
  const [status, setStatus] = useState("idle");

  const title = useMemo(() => "Cortex Knowledge Base", []);

  async function handleUpload(files, sourceType) {
    setStatus("ingesting");
    // This fetch is the ingest path; if it fails, confirm the backend is running on port 8000.
    console.log("[upload] sending files", Array.from(files).map((file) => file.name), { sourceType });
    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("files", file));
    if (sourceType) {
      formData.append("source_type", sourceType);
    }

    const response = await fetch(`${API_URL}/ingest`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      setStatus("idle");
      throw new Error("Ingest failed");
    }

    const payload = await response.json();
    console.log("[upload] ingest response", payload);
    setIngestResults(payload.results || []);
    setStatus("ready");
  }

  async function handleAsk(question) {
    const trimmed = question.trim();
    if (!trimmed) return;

    // Chat requests depend on the backend response format { answer, sources }.
    console.log("[chat] asking question", trimmed);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: trimmed, top_k: 5 }),
    });

    if (!response.ok) {
      throw new Error("Chat request failed");
    }

    const payload = await response.json();
    console.log("[chat] response payload", payload);
    setMessages((current) => [...current, { role: "assistant", content: payload.answer }]);
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      <main className="layout">
        <section className="hero">
          <p className="eyebrow">Assignment build</p>
          <h1>{title}</h1>
          <p className="lede">
            Upload LinkedIn, Twitter/X, or Instagram exports, then query the person’s own words with grounded citations.
          </p>
          <div className="status-row">
            <span className={`status-pill status-${status}`}>{status}</span>
          </div>
        </section>

        <section className="panel-grid">
          <div className="panel panel-upload">
            <FileUpload onUpload={handleUpload} />
          </div>
          <div className="panel panel-chat">
            <ChatWindow messages={messages} onAsk={handleAsk} />
          </div>
        </section>

        <section className="sources-section">
          <div className="section-head">
            <h2>Ingest Summary</h2>
            <p>Per-file ingest counts from the latest upload.</p>
          </div>
          <div className="source-grid">
            {ingestResults.length ? (
              ingestResults.map((result, index) => (
                <article className="source-card" key={`${result.filename || index}`}>
                  <div className="source-topline">
                    <span className="source-index">#{index + 1}</span>
                    <span className="source-meta">{result.filename || "upload"}</span>
                  </div>
                  <p className="source-text">
                    {result.records} records, {result.chunks} chunks, {result.inserted} inserted
                  </p>
                  <div className="source-foot">
                    <span>source file</span>
                    <span>{result.inserted ? "ready" : "empty"}</span>
                  </div>
                </article>
              ))
            ) : (
              <div className="empty-state">No ingest summary yet. Upload a file first.</div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
