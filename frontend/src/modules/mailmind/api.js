import { get, post } from "../../api/client";

const BASE = "/api/modules/mailmind";
const BACKEND = "http://localhost:8000";

export const mailmindApi = {
  // emails
  list:           () => get(`${BASE}/emails`),
  listFiltered:   (from, to, flaggedOnly) => {
    const params = new URLSearchParams();
    if (from) params.append("date_from", from);
    if (to) params.append("date_to", to);
    if (flaggedOnly) params.append("flagged_only", "true");
    return get(`${BASE}/emails?${params}`);
  },
  fetchInbox:     () => post(`${BASE}/emails/fetch`),
  summarise:      (id) => post(`${BASE}/emails/${id}/summarise`),
  summariseStream: async (id, onChunk) => {
    const res = await fetch(`${BACKEND}${BASE}/emails/${id}/summarise/stream`, { method: "POST" });
    if (!res.ok) throw new Error(`Stream failed: ${res.status}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let full = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      full += decoder.decode(value, { stream: true });
      onChunk(full);
    }
    if (!full.trim()) throw new Error("LLM returned empty response");
    return full;
  },
  getThread:      (id) => get(`${BASE}/emails/${id}/thread`),
  flag:           (id) => post(`${BASE}/emails/flag`, { email_id: id }),
  dismiss:        (id) => post(`${BASE}/emails/dismiss`, { email_id: id }),
  blockSender:    (id) => post(`${BASE}/emails/${id}/block-sender`),

  // reply
  draftReply:     (id, intent) => post(`${BASE}/reply/draft`, { email_id: id, user_intent: intent }),
  sendReply:      (id, draft) => post(`${BASE}/reply/send`, { email_id: id, draft }),

  // blocklist
  getBlocklist:   () => get(`${BASE}/blocklist`),
  addBlock:       (entry) => post(`${BASE}/blocklist/add`, { entry }),
  removeBlock:    (entry) => post(`${BASE}/blocklist/remove`, { entry }),

  // daemon
  daemonStatus:   () => get(`${BASE}/daemon/status`),
  startDaemon:    () => post(`${BASE}/daemon/start`),
  stopDaemon:     () => post(`${BASE}/daemon/stop`),
  pauseDaemon:    () => post(`${BASE}/daemon/pause`),
  resumeDaemon:   () => post(`${BASE}/daemon/resume`),

  // module settings
  getSettings:    () => get(`${BASE}/settings`),
  saveSettings:   (s) => post(`${BASE}/settings`, s),
};
