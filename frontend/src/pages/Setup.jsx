import { useState, useEffect, useRef } from "react";
import Logo from "../core/Logo";
import { authApi } from "../api/auth";
import { providersApi } from "../api/providers";
import { mailmindApi } from "../modules/mailmind/api";

const STEPS = [
  { id: "provider", label: "AI Model" },
  { id: "gmail",    label: "Gmail" },
  { id: "hours",    label: "Hours" },
  { id: "profile",  label: "Profile" },
];

export default function Setup({ onComplete }) {
  const [step, setStep] = useState(0);

  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState("ollama");
  const [providerKeys, setProviderKeys] = useState({});
  const [ollamaModels, setOllamaModels] = useState([]);
  const [selectedOllamaModel, setSelectedOllamaModel] = useState("");
  const [cloudModels, setCloudModels] = useState({});
  const [selectedCloudModels, setSelectedCloudModels] = useState({});
  const [keyTesting, setKeyTesting] = useState({});
  const [keyMessages, setKeyMessages] = useState({});

  const [gmailStatus, setGmailStatus] = useState("idle"); // idle | waiting | ok | error
  const [gmailError, setGmailError] = useState("");
  const gmailPollRef = useRef(null);

  const [workStart, setWorkStart] = useState("09:00");
  const [workEnd, setWorkEnd] = useState("18:00");
  const [userName, setUserName] = useState("");
  const [userTitle, setUserTitle] = useState("");

  useEffect(() => {
    providersApi.list()
      .then(data => {
        setProviders(data.providers || []);
        data.providers.forEach(p => {
          if (p.id === "ollama") {
            providersApi.models("ollama").then(r => {
              const models = r.models || [];
              setOllamaModels(models);
              if (models.length > 0) setSelectedOllamaModel(p.model || models[0].name);
            });
          } else {
            providersApi.models(p.id).then(r => {
              setCloudModels(prev => ({ ...prev, [p.id]: r.models || [] }));
              setSelectedCloudModels(prev => ({
                ...prev, [p.id]: p.model || (r.models?.[0]?.name || ""),
              }));
            });
          }
        });
      })
      .catch(() => {});
  }, []);

  const testKey = async (pid) => {
    const key = providerKeys[pid];
    if (!key) return;
    setKeyTesting(s => ({ ...s, [pid]: "testing" }));
    try {
      const res = await providersApi.test(pid, key);
      setKeyTesting(s => ({ ...s, [pid]: res.ok ? "ok" : "fail" }));
      setKeyMessages(s => ({ ...s, [pid]: res.message }));
    } catch (e) {
      setKeyTesting(s => ({ ...s, [pid]: "fail" }));
      setKeyMessages(s => ({ ...s, [pid]: e.message }));
    }
  };

  const connectGmail = async () => {
    setGmailError("");
    try {
      const { url } = await authApi.loginUrl();
      window.open(url, "_blank");
      setGmailStatus("waiting");
      // Poll until Google redirects back and the backend saves the token
      gmailPollRef.current = setInterval(async () => {
        try {
          const { authenticated } = await authApi.status();
          if (authenticated) {
            clearInterval(gmailPollRef.current);
            setGmailStatus("ok");
          }
        } catch {}
      }, 2000);
    } catch (e) {
      setGmailStatus("error");
      setGmailError(e.message || "Could not get sign-in URL — is client_secret.json in your workspace folder?");
    }
  };

  // Clean up poll on unmount
  useEffect(() => () => clearInterval(gmailPollRef.current), []);

  const finish = async () => {
    // Save any API keys the user entered
    for (const [pid, key] of Object.entries(providerKeys)) {
      if (key) {
        try { await providersApi.saveKey(pid, key); } catch {}
      }
    }
    // Activate chosen provider (only if reachable)
    const isCloud = selectedProvider !== "ollama";
    const hasKey = isCloud ? !!providerKeys[selectedProvider] : true;
    if (hasKey) {
      try { await providersApi.setActive(selectedProvider); } catch {}
    }
    // Save per-provider models
    if (selectedOllamaModel) {
      await providersApi.setModel("ollama", selectedOllamaModel).catch(() => {});
    }
    for (const [pid, model] of Object.entries(selectedCloudModels)) {
      if (model) await providersApi.setModel(pid, model).catch(() => {});
    }
    // Save MailMind module settings (profile, hours)
    await mailmindApi.saveSettings({
      user_name: userName || "User",
      user_title: userTitle || "Professional",
      work_start: workStart,
      work_end: workEnd,
    }).catch(() => {});
    await mailmindApi.startDaemon().catch(() => {});
    onComplete();
  };

  const canProceed = () => {
    if (step === 0) {
      if (selectedProvider === "ollama") return ollamaModels.length > 0;
      return keyTesting[selectedProvider] === "ok";
    }
    if (step === 1) return gmailStatus === "ok";
    if (step === 2) return workStart && workEnd;
    if (step === 3) return userName.trim().length > 0;
    return true;
  };

  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "1fr 1fr", background: "var(--bg-0)" }}>
      <aside style={{
        padding: "40px 48px", background: "var(--bg-1)",
        borderRight: "1px solid var(--border-subtle)",
        display: "flex", flexDirection: "column", justifyContent: "space-between",
        position: "relative", overflow: "hidden",
      }}>
        <svg width="500" height="500" viewBox="0 0 500 500"
          style={{ position: "absolute", bottom: -160, right: -160, opacity: 0.07, pointerEvents: "none" }}>
          <path d="M20 480 Q 80 240, 240 80" stroke="var(--accent)" strokeWidth="1" fill="none" />
          <path d="M60 480 Q 140 280, 300 120" stroke="var(--accent)" strokeWidth="1" fill="none" />
          <path d="M120 480 Q 200 320, 360 160" stroke="var(--accent)" strokeWidth="1" fill="none" />
          <path d="M180 480 Q 260 360, 420 200" stroke="var(--accent)" strokeWidth="1" fill="none" />
        </svg>
        <Logo size={22} />
        <div style={{ position: "relative", zIndex: 1 }}>
          <div style={{
            fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)",
            letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 14,
          }}>─ First run</div>
          <h1 style={{
            fontFamily: "var(--font-display)", fontWeight: 400, fontSize: 42,
            lineHeight: 1.1, letterSpacing: "-0.02em", color: "var(--text-0)",
            margin: 0, marginBottom: 18,
          }}>A quiet workspace<br />for your AI tools.</h1>
          <p style={{ fontSize: 14, lineHeight: 1.6, color: "var(--text-2)", maxWidth: 420, margin: 0 }}>
            Local-first by default. MailMind is the first module — more coming. Pick
            your model, connect your inbox, go.
          </p>
        </div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-3)", letterSpacing: "0.1em" }}>
          v0.2.0 · LOCAL BUILD
        </div>
      </aside>

      <main style={{ padding: "40px 48px", display: "flex", flexDirection: "column", maxWidth: 560, width: "100%" }}>
        <div style={{
          display: "flex", gap: 8, marginBottom: 32,
          fontFamily: "var(--font-mono)", fontSize: 10,
          letterSpacing: "0.08em", textTransform: "uppercase",
        }}>
          {STEPS.map((s, i) => (
            <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 6,
                color: i === step ? "var(--accent)" : i < step ? "var(--text-1)" : "var(--text-3)",
              }}>
                <span style={{
                  width: 18, height: 18, borderRadius: "50%",
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  background: i < step ? "var(--accent)" : "transparent",
                  border: "1px solid",
                  borderColor: i === step ? "var(--accent)" : i < step ? "var(--accent)" : "var(--border)",
                  color: i < step ? "#1a1410" : "inherit",
                  fontSize: 9, fontWeight: 600,
                }}>{i < step ? "✓" : i + 1}</span>
                {s.label}
              </div>
              {i < STEPS.length - 1 && <span style={{ color: "var(--text-3)" }}>·</span>}
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }}>
          {step === 0 && (
            <div>
              <h2 style={headingStyle}>Choose your model</h2>
              <p style={subheadingStyle}>
                Ollama runs locally — recommended. Cloud providers are faster but send prompts off your machine.
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 20 }}>
                {providers.map(p => {
                  const isSelected = selectedProvider === p.id;
                  const testState = keyTesting[p.id];
                  return (
                    <div key={p.id}
                      style={{
                        padding: 14, border: "1px solid",
                        borderColor: isSelected ? "var(--accent-line)" : "var(--border)",
                        background: isSelected ? "var(--accent-soft)" : "var(--bg-2)",
                        borderRadius: "var(--r-md)", cursor: "pointer", transition: "all 0.15s",
                      }}
                      onClick={() => setSelectedProvider(p.id)}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{
                          width: 14, height: 14, borderRadius: "50%",
                          border: "1.5px solid",
                          borderColor: isSelected ? "var(--accent)" : "var(--text-3)",
                          display: "inline-flex", alignItems: "center", justifyContent: "center",
                        }}>
                          {isSelected && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)" }} />}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-0)" }}>{p.display_name}</span>
                        {p.is_local ? <Tag color="var(--success)">local</Tag> : <Tag color="var(--text-3)">cloud</Tag>}
                      </div>

                      {isSelected && (
                        <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border-subtle)" }}>
                          {p.id === "ollama" ? (
                            ollamaModels.length > 0 ? (
                              <>
                                <div style={labelStyle}>Installed models</div>
                                <select value={selectedOllamaModel}
                                  onChange={e => setSelectedOllamaModel(e.target.value)}
                                  className="oc-input" style={{ fontFamily: "var(--font-mono)" }}>
                                  {ollamaModels.map(m => (
                                    <option key={m.name} value={m.name}>
                                      {m.name}{m.size > 0 ? ` · ${(m.size / 1e9).toFixed(1)}GB` : ""}
                                    </option>
                                  ))}
                                </select>
                              </>
                            ) : (
                              <div style={{
                                padding: "10px 12px", background: "var(--bg-inset)",
                                border: "1px solid var(--border)", borderRadius: "var(--r-sm)",
                                fontSize: 12, color: "var(--text-2)", lineHeight: 1.6,
                              }}>
                                Ollama not detected. Install from{" "}
                                <span style={{ color: "var(--accent)", fontFamily: "var(--font-mono)" }}>ollama.com</span>,
                                then run <code style={codeStyle}>ollama serve</code>.
                              </div>
                            )
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                              <div>
                                <div style={labelStyle}>API key</div>
                                <div style={{ display: "flex", gap: 6 }}>
                                  <input type="password" value={providerKeys[p.id] || ""}
                                    onChange={e => {
                                      setProviderKeys(s => ({ ...s, [p.id]: e.target.value }));
                                      setKeyTesting(s => ({ ...s, [p.id]: "idle" }));
                                    }}
                                    placeholder={keyPlaceholder(p.id)}
                                    className="oc-input"
                                    style={{ flex: 1, fontFamily: "var(--font-mono)" }} />
                                  <button className="oc-btn" onClick={() => testKey(p.id)}
                                    disabled={!providerKeys[p.id] || testState === "testing"}>
                                    {testState === "testing" ? "Testing…" : "Test"}
                                  </button>
                                </div>
                                {testState === "ok" && (
                                  <div style={{ marginTop: 6, fontSize: 11, color: "var(--success)" }}>
                                    ✓ {keyMessages[p.id] || "Key works"}
                                  </div>
                                )}
                                {testState === "fail" && (
                                  <div style={{ marginTop: 6, fontSize: 11, color: "var(--danger)" }}>
                                    ✗ {keyMessages[p.id] || "Invalid"}
                                  </div>
                                )}
                              </div>

                              {cloudModels[p.id]?.length > 0 && (
                                <div>
                                  <div style={labelStyle}>Model</div>
                                  <select value={selectedCloudModels[p.id] || ""}
                                    onChange={e => setSelectedCloudModels(s => ({ ...s, [p.id]: e.target.value }))}
                                    className="oc-input" style={{ fontFamily: "var(--font-mono)" }}>
                                    {cloudModels[p.id].map(m => (
                                      <option key={m.name} value={m.name}>
                                        {m.label || m.name}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {step === 1 && (
            <div>
              <h2 style={headingStyle}>Connect Gmail</h2>
              <p style={subheadingStyle}>
                Sign in with Google — no passwords to copy, no app passwords needed.
              </p>

              <div style={{
                padding: 14, marginTop: 16, marginBottom: 24,
                background: "var(--bg-2)", border: "1px solid var(--border-subtle)",
                borderRadius: "var(--r-md)", fontSize: 12, color: "var(--text-2)", lineHeight: 1.7,
              }}>
                <div style={{ color: "var(--text-1)", marginBottom: 6, fontWeight: 500 }}>One-time setup required</div>
                <div>1. Go to <span style={{ color: "var(--accent)", fontFamily: "var(--font-mono)" }}>console.cloud.google.com</span></div>
                <div>2. Create a project → Enable <span style={{ fontFamily: "var(--font-mono)" }}>Gmail API</span></div>
                <div>3. APIs & Services → Credentials → Create → OAuth 2.0 Client → Desktop App</div>
                <div>4. Download the JSON → save as <span style={{ fontFamily: "var(--font-mono)" }}>~/Desktop/openclaw-py/client_secret.json</span></div>
                <div style={{ marginTop: 8, color: "var(--text-3)" }}>Only needed once. Anyone cloning this repo does the same with their own Google account.</div>
              </div>

              {gmailStatus === "idle" && (
                <button className="oc-btn oc-btn--primary" onClick={connectGmail}
                  style={{ width: "100%", padding: "11px" }}>
                  Sign in with Google →
                </button>
              )}
              {gmailStatus === "waiting" && (
                <div>
                  <StatusPill color="var(--accent)" text="Waiting for Google sign-in… (complete it in the browser tab)" />
                  <button className="oc-btn" onClick={connectGmail}
                    style={{ width: "100%", padding: "10px", marginTop: 10, fontSize: 12 }}>
                    Open sign-in again
                  </button>
                </div>
              )}
              {gmailStatus === "ok" && <StatusPill color="var(--success)" text="✓ Gmail connected" />}
              {gmailStatus === "error" && (
                <>
                  <StatusPill color="var(--danger)" text={`✗ ${gmailError}`} />
                  <button className="oc-btn oc-btn--primary" onClick={connectGmail}
                    style={{ width: "100%", padding: "11px", marginTop: 10 }}>
                    Try again
                  </button>
                </>
              )}
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 style={headingStyle}>Working hours</h2>
              <p style={subheadingStyle}>
                MailMind only checks inbox during these hours. Outside them — idle.
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 20 }}>
                <div>
                  <div style={labelStyle}>Start</div>
                  <input type="time" value={workStart} onChange={e => setWorkStart(e.target.value)}
                    className="oc-input" style={{ fontFamily: "var(--font-mono)" }} />
                </div>
                <div>
                  <div style={labelStyle}>End</div>
                  <input type="time" value={workEnd} onChange={e => setWorkEnd(e.target.value)}
                    className="oc-input" style={{ fontFamily: "var(--font-mono)" }} />
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 style={headingStyle}>Your profile</h2>
              <p style={subheadingStyle}>Used to personalise reply drafts. The AI signs off as you.</p>
              <div style={{ marginTop: 20, marginBottom: 12 }}>
                <div style={labelStyle}>Your name</div>
                <input type="text" value={userName} onChange={e => setUserName(e.target.value)}
                  placeholder="Rishil" className="oc-input" />
              </div>
              <div style={{ marginBottom: 16 }}>
                <div style={labelStyle}>Job title (optional)</div>
                <input type="text" value={userTitle} onChange={e => setUserTitle(e.target.value)}
                  placeholder="ML Engineer" className="oc-input" />
              </div>
              <div style={{
                padding: "11px 13px", borderRadius: "var(--r-md)",
                background: "var(--accent-soft)", border: "1px solid var(--accent-line)",
                fontSize: 12, color: "var(--text-1)", lineHeight: 1.6,
              }}>
                Replies will end with:&nbsp;
                <span style={{ color: "var(--accent)", fontFamily: "var(--font-mono)" }}>
                  Best regards, {userName || "Your Name"}
                </span>
              </div>
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 28 }}>
          {step > 0 && (
            <button className="oc-btn" onClick={() => setStep(s => s - 1)} style={{ flex: 1 }}>Back</button>
          )}
          {step < STEPS.length - 1 ? (
            <button className="oc-btn oc-btn--primary" onClick={() => setStep(s => s + 1)}
              disabled={!canProceed()} style={{ flex: 2 }}>Continue →</button>
          ) : (
            <button className="oc-btn oc-btn--primary" onClick={finish}
              disabled={!canProceed()} style={{ flex: 2 }}>Launch OpenClaw-Py →</button>
          )}
        </div>
      </main>
    </div>
  );
}

/* ── shared ──────────────────────────────────────── */
const headingStyle = {
  fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 26,
  color: "var(--text-0)", letterSpacing: "-0.01em", margin: 0, marginBottom: 6,
};
const subheadingStyle = { fontSize: 13, color: "var(--text-2)", lineHeight: 1.6, margin: 0 };
const labelStyle = {
  fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-3)",
  letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6,
};
const codeStyle = {
  fontFamily: "var(--font-mono)", fontSize: 11,
  color: "var(--text-1)", background: "var(--bg-3)",
  padding: "1px 5px", borderRadius: 3,
};

function Tag({ color, children }) {
  return (
    <span style={{
      fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.08em",
      textTransform: "uppercase", color, padding: "2px 6px",
      border: "1px solid currentColor", borderRadius: 3, opacity: 0.7,
    }}>{children}</span>
  );
}

function StatusPill({ color, text }) {
  return (
    <div style={{
      padding: "11px 13px", borderRadius: "var(--r-md)",
      border: `1px solid ${color}`, background: `${color}15`,
      color, fontSize: 12, fontFamily: "var(--font-mono)",
    }}>{text}</div>
  );
}

function keyPlaceholder(pid) {
  if (pid === "claude") return "sk-ant-...";
  if (pid === "openai") return "sk-...";
  if (pid === "gemini") return "AIza...";
  return "";
}
