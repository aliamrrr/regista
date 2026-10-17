// Full class names (not built strings) so Tailwind can see every one of them.
const STAGES = [
  { name: 'Ingest', dot: 'bg-st-ingest shadow-[0_0_10px_var(--st-ingest)]' },
  { name: 'Interpret', dot: 'bg-st-interpret shadow-[0_0_10px_var(--st-interpret)]' },
  { name: 'Explain', dot: 'bg-st-explain shadow-[0_0_10px_var(--st-explain)]' },
  { name: 'Render', dot: 'bg-st-render shadow-[0_0_10px_var(--st-render)]' },
  { name: 'Personalize', dot: 'bg-st-personalize shadow-[0_0_10px_var(--st-personalize)]' },
  { name: 'Trust', dot: 'bg-st-trust shadow-[0_0_10px_var(--st-trust)]' },
] as const

/** The five pipeline stages of the brief plus the trust band, as in the vision deck. */
export function StageKey() {
  return (
    <ul aria-label="Pipeline stages" className="flex flex-wrap gap-2">
      {STAGES.map(({ name, dot }) => (
        <li
          key={name}
          className="flex items-center gap-2 rounded-full border border-line-2 bg-ink-2 px-3 py-2 font-mono text-[13px] leading-none font-semibold tracking-[0.08em] uppercase"
        >
          <span aria-hidden="true" className={`size-2.5 rounded-full ${dot}`} />
          {name}
        </li>
      ))}
    </ul>
  )
}
