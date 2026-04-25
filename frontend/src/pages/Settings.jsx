import { useState, useEffect } from "react";
import { providersApi } from "../api/providers";
import { modulesWithSettings } from "../modules/registry";

/**
 * Settings — Providers + General + one tab per registered module with a SettingsTab.
 * Completely module-agnostic: reads from the registry.
 */
export default function Settings() {
  const moduleTabs = modulesWithSettings();
  const [tab, setTab] = useState("providers");

  const tabs = [
    { id: "providers", label: "Providers" },
    { id: "general",   label: "General" },
    ...moduleTabs.map(m => ({ id: m.manifest.id, label: m.manifest.name })),
  ];

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <style>{`
        @keyframes oc-fadein { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      <div style={{ padding: "20px 32px 0", borderBottom: "1px solid var(--border-subtle)" }}>
        <h1 style={{
          fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 22,
          color: "var(--text-0)", letterSpacing: "-0.01em", margin: 0, marginBottom: 4,
        }}>Settings</h1>
        <div style={{
          fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-3)",
          letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 18,
        }}>Configure OpenClaw-Py</div>

        <div style={{ display: "flex", gap: 2 }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              style={{
                padding: "9px 16px",
                background: "transparent", border: "none",
                borderBottom: "2px solid",
                borderColor: tab === t.id ? "var(--accent)" : "transparent",
                color: tab === t.id ? "var(--text-0)" : "var(--text-2)",
                fontSize: 13, fontWeight: 500, cursor: "pointer",
                fontFamily: "var(--font-sans)", transition: "color 0.15s",
                marginBottom: -1,
              }}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "28px 32px 40px", maxWidth: 760 }}>
        <div style={{ animation: "oc-fadein 0.2s ease" }}>
          {tab === "providers" && <ProvidersTab />}
          {tab === "general"   && <GeneralTab />}
          {moduleTabs.map(m => tab === m.manifest.id && <m.SettingsTab key={m.manifest.id} />)}
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════
   PROVIDERS TAB
   ════════════════════════════════════════════════ */
function ProvidersTab() {
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState({});
  const [keyInputs, setKeyInputs] = useState({});
  const [testStates, setTestStates] = useState({});
  const [testMsgs, setTestMsgs] = useState({});
  const [saving, setSaving] = useState({});

  const load = async () => {
    const { providers } = await providersApi.list();
    setProviders(providers);
    for (const p of providers) {
      providersApi.models(p.id).then(r => {
        setModels(prev => ({ ...prev, [p.id]: r.models || [] }));
      });
    }
  };

  useEffect(() => { load(); }, []);

  const saveKey = async (pid) => {
    const key = keyInputs[pid];
    if (!key) return;
    setSaving(s => ({ ...s, [pid]: true }));
    try {
      const t = await providersApi.test(pid, key);
      if (!t.ok) {
        setTestStates(s => ({ ...s, [pid]: "fail" }));
        setTestMsgs(s => ({ ...s, [pid]: t.message }));
        setSaving(s => ({ ...s, [pid]: false }));
        return;
      }
      await providersApi.saveKey(pid, key);
      setKeyInputs(s => ({ ...s, [pid]: "" }));
      setTestStates(s => ({ ...s, [pid]: "ok" }));
      setTestMsgs(s => ({ ...s, [pid]: "Saved" }));
      await load();
    } catch (e) {
      setTestStates(s => ({ ...s, [pid]: "fail" }));
      setTestMsgs(s => ({ ...s, [pid]: e.message }));
    }
    setSaving(s => ({ ...s, [pid]: false }));
  };

  const removeKey = async (pid) => {
    if (!confirm(`Remove API key for ${pid}?`)) return;
    await providersApi.deleteKey(pid);
    setTestStates(s => ({ ...s, [pid]: "idle" }));
    await load();
  };

  const setActive = async (pid) => {
    try { await providersApi.setActive(pid); await load(); }
    catch (e) { alert(e.message); }
  };

  const setModel = async (pid, model) => {
    await providersApi.setModel(pid, model);
    await load();
  };

  return (
    <div>
      <div style={{
        padding: 14, marginBottom: 20,
        background: "var(--bg-2)", border: "1px solid var(--border-subtle)",
        borderRadius: "var(--r-md)",
        fontSize: 12, color: "var(--text-2)", lineHeight: 1.7,
      }}>
        <div style={{ color: "var(--text-1)", fontWeight: 500, marginBottom: 4 }}>Privacy note</div>
        OpenClaw-Py defaults to Ollama (local). Cloud providers only activate when you
        explicitly select them. API keys are encrypted and stored locally in your workspace folder.
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {providers.map(p => {
          const isActive = p.active;
          const hasKey = p.has_key;
          const pmodels = models[p.id] || [];
          return (
            <div key={p.id} style={{
              padding: 18, background: "var(--bg-1)",
              border: "1px solid",
              borderColor: isActive ? "var(--accent-line)" : "var(--border-subtle)",
              borderRadius: "var(--r-md)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: "50%",
                      background: p.configured ? "var(--success)" : "var(--text-3)",
                    }} />
                    <span style={{
                      fontSize: 15, fontWeight: 500, color: "var(--text-0)",
                      fontFamily: "var(--font-display)",
                    }}>{p.display_name}</span>
                    {p.is_local ? <Tag color="var(--success)">local</Tag> : <Tag color="var(--text-3)">cloud</Tag>}
                    {isActive && <Tag color="var(--accent)">active</Tag>}
                  </div>
                </div>
                {!isActive && p.configured && (
                  <button className="oc-btn" onClick={() => setActive(p.id)} style={{ fontSize: 12 }}>
                    Set active
                  </button>
                )}
              </div>

              {p.requires_api_key && (
                <div style={{ marginBottom: 14 }}>
                  <div style={labelStyle}>API key</div>
                  {hasKey ? (
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <div style={{
                        flex: 1, padding: "8px 12px",
                        background: "var(--bg-inset)", border: "1px solid var(--border)",
                        borderRadius: "var(--r-md)",
                        color: "var(--text-2)", fontSize: 12, fontFamily: "var(--font-mono)",
                      }}>•••••••••••••••••••••••••• (saved)</div>
                      <button className="oc-btn oc-btn--danger" onClick={() => removeKey(p.id)} style={{ fontSize: 12 }}>
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div>
                      <div style={{ display: "flex", gap: 6 }}>
                        <input type="password" value={keyInputs[p.id] || ""}
                          onChange={e => {
                            setKeyInputs(s => ({ ...s, [p.id]: e.target.value }));
                            setTestStates(s => ({ ...s, [p.id]: "idle" }));
                          }}
                          placeholder={keyPlaceholder(p.id)}
                          className="oc-input"
                          style={{ flex: 1, fontFamily: "var(--font-mono)" }} />
                        <button className="oc-btn oc-btn--primary"
                          onClick={() => saveKey(p.id)}
                          disabled={!keyInputs[p.id] || saving[p.id]}>
                          {saving[p.id] ? "Saving…" : "Save"}
                        </button>
                      </div>
                      {testStates[p.id] === "fail" && (
                        <div style={{ marginTop: 6, fontSize: 11, color: "var(--danger)" }}>
                          ✗ {testMsgs[p.id]}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {pmodels.length > 0 && (hasKey || !p.requires_api_key) && (
                <div>
                  <div style={labelStyle}>Model</div>
                  <select value={p.model || ""} onChange={e => setModel(p.id, e.target.value)}
                    className="oc-input" style={{ fontFamily: "var(--font-mono)" }}>
                    {pmodels.map(m => (
                      <option key={m.name} value={m.name}>
                        {m.label || m.name}
                        {m.size > 0 ? ` · ${(m.size / 1e9).toFixed(1)}GB` : ""}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {p.id === "ollama" && pmodels.length === 0 && (
                <div style={{
                  padding: 12, background: "var(--bg-inset)",
                  border: "1px solid var(--border)", borderRadius: "var(--r-sm)",
                  fontSize: 12, color: "var(--text-2)", lineHeight: 1.6,
                }}>
                  Ollama not running. Start it with <code style={codeStyle}>ollama serve</code>{" "}
                  and pull a model like <code style={codeStyle}>ollama pull qwen2.5:1.5b</code>.
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════
   GENERAL TAB — app-level stuff (intentionally minimal)
   ════════════════════════════════════════════════ */
function GeneralTab() {
  return (
    <div>
      <h3 style={sectionHeadingStyle}>About</h3>
      <p style={sectionSubStyle}>
        OpenClaw-Py is a local-first AI workspace. Each module is self-contained —
        add new ones in <code style={codeStyle}>frontend/src/modules/</code>.
      </p>
      <div style={{ marginTop: 20 }}>
        <div style={labelStyle}>Data directory</div>
        <code style={{ ...codeStyle, display: "inline-block", padding: "6px 10px" }}>
          ~/Desktop/openclaw-py/
        </code>
      </div>
    </div>
  );
}

/* ── shared ─────────────────────────────────────── */
const labelStyle = {
  fontFamily: "var(--font-mono)", fontSize: 10,
  color: "var(--text-3)", letterSpacing: "0.08em",
  textTransform: "uppercase", marginBottom: 6,
};

const sectionHeadingStyle = {
  fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 16,
  color: "var(--text-0)", margin: 0, marginBottom: 4,
};

const sectionSubStyle = {
  fontSize: 13, color: "var(--text-2)", margin: 0, lineHeight: 1.6,
};

const codeStyle = {
  fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-1)",
  background: "var(--bg-3)", padding: "1px 5px", borderRadius: 3,
};

function Tag({ color, children }) {
  return (
    <span style={{
      fontFamily: "var(--font-mono)", fontSize: 9,
      letterSpacing: "0.08em", textTransform: "uppercase",
      color, padding: "2px 6px",
      border: `1px solid ${color}`, borderRadius: 3, opacity: 0.85,
    }}>{children}</span>
  );
}

function keyPlaceholder(pid) {
  if (pid === "claude") return "sk-ant-...";
  if (pid === "openai") return "sk-...";
  if (pid === "gemini") return "AIza...";
  return "";
}
