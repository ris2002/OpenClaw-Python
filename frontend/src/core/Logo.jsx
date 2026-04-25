export default function Logo({ size = 20, showWordmark = true }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
        <path d="M4 20 Q 6 10, 12 6" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M9 21 Q 10 12, 14 5" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" opacity="0.75" />
        <path d="M15 21 Q 14 13, 18 7" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" opacity="0.5" />
      </svg>
      {showWordmark && (
        <span style={{
          fontFamily: "var(--font-display)",
          fontWeight: 500,
          fontSize: 16,
          letterSpacing: "-0.01em",
          color: "var(--text-0)",
        }}>
          OpenClaw-Py
        </span>
      )}
    </div>
  );
}
