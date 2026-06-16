/**
 * nQuire brand mark — self-contained SVG, no external assets needed.
 * Props:
 *   size   – icon side length in px (default 36)
 *   showName – render the wordmark next to the icon (default false)
 *   nameSize – tailwind text-* class for the wordmark (default 'text-sm')
 */
const NQuireLogo = ({ size = 36, showName = false, nameSize = 'text-sm', onClick = () => {} }) => {
  const id = `nq-${size}`;   // unique gradient ID per size variant
  return (
    <div onClick={onClick} className={`flex items-center gap-2.5 shrink-0 ${onClick ? 'cursor-pointer hover:opacity-85 transition-opacity' : ''}`}>
      {/* ─── Badge icon ─────────────────────────────────────────── */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ flexShrink: 0 }}
      >
        <defs>
          {/* Main badge gradient — deep navy → rich indigo */}
          <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%"   stopColor="#0f1e5c" />
            <stop offset="55%"  stopColor="#3730a3" />
            <stop offset="100%" stopColor="#1d4ed8" />
          </linearGradient>
          {/* Inner highlight — subtle top-left sheen */}
          <linearGradient id={`${id}-shine`} x1="0" y1="0" x2="20" y2="20" gradientUnits="userSpaceOnUse">
            <stop offset="0%"   stopColor="#ffffff" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0"    />
          </linearGradient>
        </defs>

        {/* Badge background */}
        <rect width="40" height="40" rx="11" fill={`url(#${id}-bg)`} />
        {/* Sheen overlay */}
        <rect width="40" height="40" rx="11" fill={`url(#${id}-shine)`} />

        {/* ── Letterform: bold lowercase "n" ── */}
        {/* Left stem */}
        <rect x="8" y="14" width="4.5" height="16" rx="2.2" fill="white" />
        {/* Arch bridge + right stem */}
        <path
          d="M12.5 17.5 C12.5 14 17 12.5 19.8 14 C22.6 15.5 22.5 17.5 22.5 19.5 L22.5 30 L18 30 L18 20 C18 19 17 17.5 15.2 17.5 L12.5 17.5 Z"
          fill="white"
        />
        {/* Right stem of "n" */}
        <rect x="18" y="14" width="4.5" height="16" rx="2.2" fill="white" />

        {/* ── Accent dot — sky-blue query spark ── */}
        {/* Main dot */}
        <circle cx="31" cy="11" r="5.5" fill="#38bdf8" />
        {/* Dot inner highlight */}
        <circle cx="29.5" cy="9.5" r="1.8" fill="white" fillOpacity="0.45" />

        {/* Small question-mark tick inside accent dot */}
        <circle cx="31" cy="13.2" r="0.8" fill="white" />
        <path d="M31 8.5 C31 8.5 31 10.5 29.8 11.5" stroke="white" strokeWidth="1.3" strokeLinecap="round" />
      </svg>

      {/* ─── Wordmark ───────────────────────────────────────────── */}
      {showName && (
        <span
          className={`font-black tracking-tight leading-none ${nameSize}`}
          style={{
            background: 'linear-gradient(120deg, #e2e8f8 30%, #93c5fd 70%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          n<span style={{ WebkitTextFillColor: '#38bdf8' }}>Q</span>uire<span style={{ WebkitTextFillColor: 'rgba(148,163,184,0.45)', fontWeight: 600 }}>.ai</span>
        </span>
      )}
    </div>
  );
};

export default NQuireLogo;
