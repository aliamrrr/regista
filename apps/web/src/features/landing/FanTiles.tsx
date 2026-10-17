interface FanTile {
  lang: 'en' | 'fr' | 'es' | 'ar'
  mode: string
  line: string
}

// Persona modes from docs/SPEC.md §3, each written natively in its own language.
const TILES: readonly FanTile[] = [
  { lang: 'en', mode: 'Analyst', line: 'One match. Every fan gets their own broadcast.' },
  { lang: 'fr', mode: 'Supporter', line: 'Un match. À chaque supporter sa retransmission.' },
  { lang: 'es', mode: 'Modo jugador', line: 'Un partido. Cada aficionado, su propia retransmisión.' },
  { lang: 'ar', mode: 'وصف صوتي', line: 'مباراة واحدة. لكل مشجع بثّه الخاص.' },
]

/** The split-view idea in miniature: one message, four fans, four languages (AR is RTL). */
export function FanTiles() {
  return (
    <section aria-labelledby="fan-tiles-title" className="flex flex-col gap-3">
      <h2
        id="fan-tiles-title"
        className="font-display text-xl font-bold tracking-[0.08em] text-mist uppercase"
      >
        One line · four fans
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {TILES.map(({ lang, mode, line }) => (
          <article
            key={lang}
            lang={lang}
            dir={lang === 'ar' ? 'rtl' : 'ltr'}
            className="flex flex-col gap-3 rounded-xl border border-line bg-ink-3 p-4"
          >
            <p className="flex items-center gap-2 text-[13px] font-semibold text-mist">
              <span
                dir="ltr"
                className="rounded bg-st-personalize px-1.5 py-1 font-mono text-[11px] leading-none font-bold tracking-[0.06em] text-ink uppercase"
              >
                {lang}
              </span>
              {mode}
            </p>
            <p
              className={`text-[15px] font-semibold ${lang === 'ar' ? 'leading-relaxed' : 'leading-snug'}`}
            >
              {line}
            </p>
          </article>
        ))}
      </div>
    </section>
  )
}
