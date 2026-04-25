/**
 * MailMind module — registry entry.
 *
 * Every OpenClaw-Py module exports:
 *   manifest:     { id, name, description }
 *   Component:    main React component rendered when the module is active
 *   SettingsTab:  React component rendered inside Settings (optional)
 *   icon:         ({size, color}) => SVG (optional; Shell falls back to default)
 */

import MailMind from "./MailMind";
import MailMindSettings from "./MailMindSettings";

export const manifest = {
  id: "mailmind",
  name: "MailMind",
  description: "Inbox triage with AI summaries and reply drafts",
};

export const Component = MailMind;
export const SettingsTab = MailMindSettings;

export function icon({ size = 16, color = "currentColor" } = {}) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="1.5" />
      <path d="M3 7l9 6 9-6" />
    </svg>
  );
}
