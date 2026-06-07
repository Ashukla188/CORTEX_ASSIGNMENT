import { useState } from "react";

const SOURCE_TYPES = [
  { value: "", label: "Select source type" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "twitter", label: "Twitter/X" },
  { value: "instagram", label: "Instagram" },
];

export default function FileUpload({ onUpload }) {
  const [dragging, setDragging] = useState(false);
  const [files, setFiles] = useState([]);
  const [sourceType, setSourceType] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const accept = sourceType === "linkedin" ? ".csv" : sourceType === "instagram" ? ".json,.html" : sourceType === "twitter" ? ".json" : ".csv,.json,.html";

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    const dropped = Array.from(event.dataTransfer.files || []);
    setFiles(dropped);
  }

  async function submit(event) {
    event.preventDefault();
    if (!files.length) {
      setMessage("Select at least one file.");
      return;
    }
    if (!sourceType) {
      setMessage("Select a source type before uploading.");
      return;
    }
    if (sourceType === "linkedin" && files.some((file) => !file.name.toLowerCase().endsWith(".csv"))) {
      setMessage("LinkedIn uploads must be CSV files.");
      return;
    }

    // If the upload hangs here, the backend ingest endpoint is the first thing to check.
    console.log("[upload-form] submit", { files: files.map((file) => file.name), sourceType });
    setBusy(true);
    setMessage("");
    try {
      await onUpload(files, sourceType);
      setMessage(`Ingested ${files.length} file(s).`);
    } catch (error) {
      setMessage(error.message || "Upload failed.");
      console.error("[upload-form] upload failed", error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="upload-card" onSubmit={submit}>
      <div className="section-head compact">
        <h2>Ingest exports</h2>
        <p>Drop CSV, JSON, or HTML export files here.</p>
      </div>

      <label
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragEnter={() => setDragging(true)}
        onDragLeave={() => setDragging(false)}
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
      >
        <input
          type="file"
          multiple
          accept={accept}
          onChange={(event) => setFiles(Array.from(event.target.files || []))}
        />
        <span className="dropzone-title">Drag and drop files</span>
        <span className="dropzone-subtitle">{files.length ? `${files.length} file(s) selected` : "or click to browse"}</span>
      </label>

      <label className="field">
        <span>Source type</span>
        <select value={sourceType} onChange={(event) => setSourceType(event.target.value)} required>
          {SOURCE_TYPES.map((option) => (
            <option key={option.value} value={option.value} disabled={option.value === ""}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <button type="submit" disabled={busy}>
        {busy ? "Uploading..." : "Start ingest"}
      </button>

      {message ? <p className="helper-text">{message}</p> : null}
    </form>
  );
}
