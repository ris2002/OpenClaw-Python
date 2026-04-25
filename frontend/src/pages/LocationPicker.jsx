import { useState, useEffect } from "react";
import Logo from "../core/Logo";
import { setupApi } from "../api/setup";

export default function LocationPicker({ onConfirmed }) {
  const [path, setPath] = useState("");
  const [defaultPath, setDefaultPath] = useState("");
  const [status, setStatus] = useState("idle"); // idle | saving | error
  const [error, setError] = useState("");

  useEffect(() => {
    setupApi.status()
      .then(s => {
        setDefaultPath(s.default_dir);
        setPath(s.default_dir);
      })
      .catch(() => {});
  }, []);

  const confirm = async () => {
    setStatus("saving");
    setError("");
    try {
      await setupApi.setLocation(path.trim() || defaultPath);
      setStatus("idle");
      onConfirmed();
    } catch (e) {
      setStatus("error");
      setError(e.message || "Could not create the folder — check the path and try again.");
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex",
      alignItems: "center", justifyContent: "center",
      background: "var(--bg-0)",
    }}>
      <div style={{ width: "100%", maxWidth: 520, padding: "0 24px" }}>
        <div style={{ marginBottom: 32 }}>
          <Logo size={22} />
        </div>

        <div style={{
          fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)",
          letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 14,
        }}>─ First run</div>

        <h1 style={{
          fontFamily: "var(--font-display)", fontWeight: 400, fontSize: 32,
          lineHeight: 1.15, letterSpacing: "-0.02em",
          color: "var(--text-0)", margin: 0, marginBottom: 16,
        }}>
          Choose your workspace folder
        </h1>

        <p style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.7, margin: 0, marginBottom: 28 }}>
          OpenClaw-Py stores everything locally — your emails, AI summaries, encryption
          keys, and settings. Nothing leaves your machine. We need one folder to put
          it all in.
        </p>

        <div style={{
          padding: 16, marginBottom: 24,
          background: "var(--bg-1)", border: "1px solid var(--border-subtle)",
          borderRadius: "var(--r-md)", fontSize: 12, color: "var(--text-2)", lineHeight: 1.7,
        }}>
          <div style={{ color: "var(--text-1)", fontWeight: 500, marginBottom: 8 }}>What goes in this folder:</div>
          <div>· <span style={{ color: "var(--text-1)" }}>Encryption keys</span> — your API keys and Gmail token, Fernet-encrypted</div>
          <div>· <span style={{ color: "var(--text-1)" }}>Email store</span> — cached emails, summaries, flags (JSON)</div>
          <div>· <span style={{ color: "var(--text-1)" }}>Settings</span> — your preferences and profile</div>
          <div>· <span style={{ color: "var(--text-1)" }}>ChromaDB</span> — optional vector store for flagged conversations</div>
          <div style={{ marginTop: 8, color: "var(--text-3)", fontSize: 11 }}>
            This folder is never touched by git. Delete it to fully reset the app.
          </div>
        </div>

        <div style={{
          fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-3)",
          letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6,
        }}>Folder path</div>
        <input
          type="text"
          value={path}
          onChange={e => setPath(e.target.value)}
          className="oc-input"
          style={{ marginBottom: 8, fontFamily: "var(--font-mono)", fontSize: 12 }}
          placeholder={defaultPath}
        />
        <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 24 }}>
          Default is your Desktop. Type any absolute path — the folder will be created if it doesn't exist.
        </div>

        {error && (
          <div style={{
            padding: "10px 13px", marginBottom: 16,
            background: "rgba(201,112,100,0.08)", border: "1px solid rgba(201,112,100,0.3)",
            borderRadius: "var(--r-sm)", fontSize: 12, color: "var(--danger)",
          }}>{error}</div>
        )}

        <button
          className="oc-btn oc-btn--primary"
          onClick={confirm}
          disabled={status === "saving"}
          style={{ width: "100%", padding: "12px", fontSize: 13 }}
        >
          {status === "saving" ? "Creating folder…" : "Create my workspace →"}
        </button>
      </div>
    </div>
  );
}
