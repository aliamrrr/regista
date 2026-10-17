/** REGISTA wordmark with the broadcast-frame mark from the vision deck. */
export function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="size-7 text-flood"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 9V5h4M16 5h4v4M20 15v4h-4M8 19H4v-4" />
        <circle cx="12" cy="12" r="2.8" fill="currentColor" stroke="none" />
      </svg>
      <span className="font-display text-2xl leading-none font-extrabold tracking-[0.1em]">
        REGISTA
      </span>
    </div>
  )
}
