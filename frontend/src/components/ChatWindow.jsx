import { useState } from "react";

export default function ChatWindow({ messages, onAsk }) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (!question.trim()) return;
    // If this button sends nothing, verify the form state and the /chat endpoint response.
    console.log("[chat-form] submit", question);
    setBusy(true);
    try {
      await onAsk(question);
      setQuestion("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-card">
      <div className="section-head compact">
        <h2>Ask the person</h2>
        <p>Grounded answers only, with cited source chunks below.</p>
      </div>

      <div className="message-list">
        {messages.map((message, index) => (
          <div key={index} className={`message message-${message.role}`}>
            <div className="message-role">{message.role}</div>
            <div className="message-body">{message.content}</div>
          </div>
        ))}
      </div>

      <form className="chat-form" onSubmit={submit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder='Ask something like "What does this person think about remote work?"'
        />
        <button type="submit" disabled={busy}>
          {busy ? "Sending..." : "Ask"}
        </button>
      </form>
    </div>
  );
}
