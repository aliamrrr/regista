import { BrandMark } from '../../components/BrandMark.tsx'
import { CoreStatusPill } from '../../components/CoreStatusPill.tsx'
import { StageKey } from '../../components/StageKey.tsx'
import { FanTiles } from './FanTiles.tsx'

/** Phase 0 landing: brand, pitch, pipeline stages and a live link to regista-core. */
export function LandingPlaceholder() {
  return (
    <div className="stadium-glow flex min-h-dvh flex-col">
      <header className="flex flex-wrap items-center justify-between gap-4 px-4 py-5 sm:px-10">
        <BrandMark />
        <CoreStatusPill />
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-10 px-4 pt-8 pb-16 sm:px-10 sm:pt-14">
        <div className="flex flex-col gap-4">
          <p className="font-mono text-sm font-semibold tracking-[0.16em] text-flood uppercase">
            AI production gallery · first build
          </p>
          <h1 className="font-display text-5xl leading-[0.95] font-extrabold uppercase sm:text-7xl">
            One match.
            <br />
            Every fan gets their own broadcast.
          </h1>
          <p className="max-w-2xl text-lg leading-relaxed text-mist">
            A team of AI agents turns one stream of synthetic match events into a personalized,
            explainable, multilingual broadcast for every fan, and a verified feed the studio
            producer approves before it goes on air.
          </p>
        </div>
        <StageKey />
        <FanTiles />
      </main>

      <footer className="px-4 pb-6 font-mono text-xs text-mist sm:px-10">
        Synthetic data only · fictional league, clubs and players
      </footer>
    </div>
  )
}
