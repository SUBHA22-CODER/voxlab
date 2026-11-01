export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="8" fill="#0c0c0f" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="7.5" fill="none" stroke="#2a2a30" />
      <g stroke="#34d399" strokeWidth="2.4" strokeLinecap="round">
        <line x1="7" y1="13" x2="7" y2="19" />
        <line x1="12" y1="9" x2="12" y2="23" />
        <line x1="17" y1="11" x2="17" y2="21" />
        <line x1="22" y1="7" x2="22" y2="25" />
      </g>
      <line x1="27" y1="14" x2="27" y2="18" stroke="#3f3f46" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}
