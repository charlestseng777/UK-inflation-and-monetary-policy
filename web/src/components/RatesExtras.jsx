// Gilt market, policy pricing and positioning panels for the rates and
// positioning tabs — the UK counterpart of the Fed dashboard's sections,
// built on the same SeriesChart / DailyRangeSlider components.

import { PALETTE } from '../lib/series.js'
import { bp, contracts, dayLong, dayShort, deltaArrow, deltaTone, pct } from '../lib/format.js'

// Validated slot order (see lib/series.js): blue, orange, aqua, yellow,
// magenta, green, violet, red.
const S = {
  blue: PALETTE.headline, orange: PALETTE.policy, aqua: PALETTE.services, yellow: PALETTE.goods,
  magenta: PALETTE.food, green: PALETTE.energy, violet: PALETTE.core, red: PALETTE.alcohol,
}

export const GILT_SERIES = [
  { id: 'gilt_2y', label: '2Y gilt', short: '2Y', color: S.blue, width: 2, locked: true },
  { id: 'gilt_10y', label: '10Y gilt', short: '10Y', color: S.orange, width: 2, locked: true },
  { id: 'gilt_5y', label: '5Y gilt', short: '5Y', color: S.aqua, width: 1.5, on: true },
  { id: 'gilt_30y', label: '30Y gilt', short: '30Y', color: S.yellow, width: 1.5, on: true },
  { id: 'bank_rate', label: 'Bank Rate', short: 'Bank Rate', color: PALETTE.other, width: 1.5, step: true, on: true },
  { id: 'sonia', label: 'SONIA', short: 'SONIA', color: S.violet, width: 1.25 },
]

export const CURVE_SERIES = [
  { id: 's2s10', label: '2s10s (bp)', short: '2s10s', color: S.blue, width: 2, locked: true },
  { id: 's5s30', label: '5s30s (bp)', short: '5s30s', color: S.orange, width: 2, locked: true },
]

export const BREAKEVEN_SERIES = [
  { id: 'be_5y', label: '5Y implied RPI inflation', short: '5Y BE', color: S.blue, width: 2, locked: true },
  { id: 'be_5y5y', label: '5y5y forward implied inflation', short: '5y5y', color: S.orange, width: 2, locked: true },
  { id: 'be_10y', label: '10Y implied RPI inflation', short: '10Y BE', color: S.aqua, width: 1.5, on: true },
  { id: 'real_10y', label: '10Y real yield (index-linked)', short: '10Y real', color: S.yellow, width: 1.5 },
]

export const SPREAD_SERIES = [
  { id: 'gilt_ois_5y', label: '5Y gilt − 5Y SONIA OIS (bp)', short: 'Gilt−OIS 5Y', color: S.blue, width: 2, locked: true },
]

export const OIS_SERIES = [
  { id: 'ois_1y', label: '1Y SONIA OIS', short: '1Y OIS', color: S.blue, width: 2, locked: true },
  { id: 'ois_2y', label: '2Y SONIA OIS', short: '2Y OIS', color: S.orange, width: 2, locked: true },
  { id: 'ois_5y', label: '5Y SONIA OIS', short: '5Y OIS', color: S.aqua, width: 1.5, on: true },
  { id: 'bank_rate', label: 'Bank Rate', short: 'Bank Rate', color: PALETTE.other, width: 1.5, step: true, on: true },
]

export const PRICED_SERIES = [
  { id: 'priced_12m', label: 'Change in SONIA priced over the next 12m (bp)', short: 'Priced 12m', color: S.blue, width: 2, locked: true },
]

export const CONTRACT_COLORS = [S.blue, S.orange, S.aqua, S.yellow, S.magenta, S.green, S.violet, S.red]

// ---------------------------------------------------------------------------

/** Headline tiles, same shape as the Fed dashboard's. */
export function KpiCards({ cards }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {cards.map((card) => (
        <div key={card.id} className="card card-pad animate-fade-up">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: card.color }} aria-hidden="true" />
            <span className="label-xs">{card.label}</span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="num text-3xl font-semibold leading-none text-ink">
              {card.value === null || card.value === undefined ? '—' : card.value.toFixed(card.digits ?? 2)}
            </span>
            <span className="text-base text-faint">{card.unit}</span>
          </div>
          <div className={`mt-2 flex items-center gap-1.5 text-xs ${deltaTone(card.change)}`}>
            <span aria-hidden="true">{deltaArrow(card.change)}</span>
            <span className="num">{card.changeFormat(card.change)}</span>
            <span className="text-faint">{card.changeLabel}</span>
          </div>
          <div className="mt-1.5 text-[11px] leading-snug text-faint">{card.note}</div>
        </div>
      ))}
    </div>
  )
}

function Th({ children, right }) {
  return <th className={`px-3 py-2 text-[10px] font-medium uppercase tracking-[0.12em] text-faint ${right ? 'text-right' : 'text-left'}`}>{children}</th>
}

function Td({ children, right, className = '' }) {
  return <td className={`px-3 py-2 text-xs ${right ? 'num text-right' : ''} ${className}`}>{children}</td>
}

const toneOf = (v) => (v === null || v === undefined || v === 0 ? 'text-faint' : v > 0 ? 'text-[#E9B872]' : 'text-[#7FB9E8]')

function Table({ title, subtitle, children, footer, minWidth = 'min-w-[520px]' }) {
  return (
    <section className="card" aria-label={title}>
      <header className="border-b border-hairline px-4 py-3.5 sm:px-5">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 max-w-3xl text-xs text-muted">{subtitle}</p>}
      </header>
      <div className="overflow-x-auto scroll-thin">
        <table className={`w-full ${minWidth} border-collapse`}>{children}</table>
      </div>
      {footer && <footer className="border-t border-hairline px-4 py-3 text-[11px] leading-relaxed text-faint sm:px-5">{footer}</footer>}
    </section>
  )
}

export function GiltSnapshot({ snapshot }) {
  const rows = [
    ['gilt_2y', '2Y gilt', 'yield'], ['gilt_5y', '5Y gilt', 'yield'], ['gilt_10y', '10Y gilt', 'yield'],
    ['gilt_30y', '30Y gilt', 'yield'], ['s2s10', '2s10s', 'spread'], ['s5s30', '5s30s', 'spread'],
    ['gilt_ois_5y', '5Y gilt − OIS', 'spread'], ['ois_1y', '1Y SONIA OIS', 'yield'], ['ois_2y', '2Y SONIA OIS', 'yield'],
    ['ois_5y', '5Y SONIA OIS', 'yield'], ['be_5y', '5Y implied RPI', 'yield'], ['be_5y5y', '5y5y implied RPI', 'yield'],
    ['real_10y', '10Y real (index-linked)', 'yield'], ['sonia', 'SONIA', 'yield'], ['bank_rate', 'Bank Rate', 'yield'],
  ]
  return (
    <Table
      title="Gilt market snapshot"
      subtitle="Latest close and change, in basis points. Spreads are already in bp."
      footer="Zero-coupon spot rates from the Bank of England's fitted nominal, real, implied-inflation and OIS curves, published with a lag of about one business day. Implied inflation is RPI-based, so it runs above CPI."
    >
      <thead className="border-b border-hairline">
        <tr><Th>Instrument</Th><Th right>Level</Th><Th right>1 week</Th><Th right>1 month</Th><Th right>As of</Th></tr>
      </thead>
      <tbody>
        {rows.map(([id, label, kind]) => {
          const s = snapshot?.[id]
          if (!s || s.value === null || s.value === undefined) return null
          const scale = kind === 'spread' ? 1 : 100
          const w = s.chg_1w === null ? null : s.chg_1w * scale
          const m = s.chg_1m === null ? null : s.chg_1m * scale
          return (
            <tr key={id} className="border-b border-hairline/60 last:border-0">
              <Td className="text-ink">{label}</Td>
              <Td right className="text-ink">{kind === 'spread' ? bp(s.value, 1) : pct(s.value, 2)}</Td>
              <Td right className={toneOf(w)}>{bp(w, 1)}</Td>
              <Td right className={toneOf(m)}>{bp(m, 1)}</Td>
              <Td right className="text-faint">{dayShort(s.date)}</Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

export function OisCurveTable({ curve }) {
  const points = curve?.points ?? []
  if (!points.length) return null
  return (
    <Table
      title="SONIA OIS curve"
      subtitle={`Bank of England OIS spot curve, ${curve.as_of ? dayLong(curve.as_of) : ''}. Against SONIA (${pct(curve.sonia, 2)}).`}
      footer="A tenor above SONIA means the market prices SONIA higher on average over that horizon (hikes); below means cuts. Read off the same curve, in the same discount-factor space, as the synthetic MPC OIS curve above."
      minWidth="min-w-[360px]"
    >
      <thead className="border-b border-hairline"><tr><Th>Tenor</Th><Th right>Rate</Th><Th right>vs SONIA</Th></tr></thead>
      <tbody>
        {points.map((p) => (
          <tr key={p.tenor} className="border-b border-hairline/60 last:border-0">
            <Td className="text-ink">{p.tenor}</Td>
            <Td right className="text-ink">{pct(p.rate, 3)}</Td>
            <Td right className={toneOf(p.vs_sonia_bp)}>{bp(p.vs_sonia_bp, 1)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

/** Refinitiv MPC-dated OIS, shown next to — not instead of — the synthetic curve. */
export function MpcOisTable({ data, status }) {
  const rows = data?.meetings ?? []
  if (!rows.length) {
    const reason = status?.error === 'no credentials configured'
      ? 'Add REFINITIV_USERNAME, REFINITIV_PASSWORD and REFINITIV_APP_KEY as repository secrets to show meeting-dated OIS from Refinitiv here.'
      : `Refinitiv MPC-dated OIS unavailable this run${status?.error ? ` (${status.error})` : ''}.`
    return (
      <section className="card card-pad" aria-label="Refinitiv MPC-dated OIS">
        <div className="label-xs">Refinitiv MPC-dated OIS</div>
        <p className="mt-2 text-xs leading-relaxed text-muted">{reason}</p>
        <p className="mt-2 text-[11px] leading-relaxed text-faint">
          The synthetic MPC OIS curve above bootstraps the same meeting-by-meeting path from the
          Bank of England's public curve, so it stays available either way.
        </p>
      </section>
    )
  }
  return (
    <Table
      title="MPC-dated OIS (Refinitiv)"
      subtitle={`Meeting-dated SONIA OIS: each contract runs from one MPC meeting to the next. Moves against SONIA (${pct(data.reference_sonia, 2)}).`}
      footer="A direct market quote of the step priced at each meeting, for comparison with the synthetic curve bootstrapped from the Bank's public OIS curve. Latest close from Refinitiv historical pricing."
    >
      <thead className="border-b border-hairline">
        <tr><Th>From meeting</Th><Th right>Rate</Th><Th right>Change</Th><Th right>Cumulative</Th><Th right>RIC</Th></tr>
      </thead>
      <tbody>
        {rows.map((m) => (
          <tr key={m.ric} className="border-b border-hairline/60 last:border-0">
            <Td className="text-ink">{m.meeting ? dayLong(m.meeting) : '—'}</Td>
            <Td right className="text-ink">{pct(m.rate, 3)}</Td>
            <Td right className={toneOf(m.change_bp)}>{bp(m.change_bp, 1)}</Td>
            <Td right className={toneOf(m.cumulative_bp)}>{bp(m.cumulative_bp, 1)}</Td>
            <Td right className="text-faint">{m.ric}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

export function PositioningTable({ positioning }) {
  const latest = positioning?.latest ?? []
  if (!latest.length) return null
  const zTone = (z) => (z === null || z === undefined ? 'text-faint' : Math.abs(z) >= 1.5 ? 'text-ink font-semibold' : 'text-muted')
  return (
    <Table
      title="Sterling futures positioning & crowding"
      subtitle={`CFTC Traders in Financial Futures, week of ${positioning?.as_of ? dayLong(positioning.as_of) : '—'}. Net contracts; z-scores and percentiles against the past 3 years.`}
      footer="Gilt futures trade on ICE Futures Europe, which the CFTC doesn't cover, so this is sterling FX and CME SONIA futures positioning — the closest public read on how crowded a UK rates view is. |z| ≥ 1.5 is shown in bold as crowded."
      minWidth="min-w-[760px]"
    >
      <thead className="border-b border-hairline">
        <tr>
          <Th>Contract</Th><Th right>Lev funds net</Th><Th right>w/w</Th><Th right>z (3y)</Th><Th right>Pctile</Th>
          <Th right>Asset mgr net</Th><Th right>w/w</Th><Th right>z (3y)</Th><Th right>% OI (lev)</Th>
        </tr>
      </thead>
      <tbody>
        {latest.map((c, i) => (
          <tr key={c.id} className="border-b border-hairline/60 last:border-0">
            <Td className="text-ink">
              <span className="mr-2 inline-block h-2 w-2 rounded-sm" style={{ backgroundColor: CONTRACT_COLORS[i % CONTRACT_COLORS.length] }} aria-hidden="true" />
              {c.label}
            </Td>
            <Td right className="text-ink">{contracts(c.lev_net)}</Td>
            <Td right className={toneOf(c.lev_change)}>{contracts(c.lev_change)}</Td>
            <Td right className={zTone(c.lev_z)}>{c.lev_z?.toFixed(2) ?? '—'}</Td>
            <Td right className="text-muted">{c.lev_pctile ?? '—'}</Td>
            <Td right className="text-ink">{contracts(c.am_net)}</Td>
            <Td right className={toneOf(c.am_change)}>{contracts(c.am_change)}</Td>
            <Td right className={zTone(c.am_z)}>{c.am_z?.toFixed(2) ?? '—'}</Td>
            <Td right className="text-muted">{c.lev_pct_oi === null || c.lev_pct_oi === undefined ? '—' : `${c.lev_pct_oi.toFixed(1)}%`}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

export function GiltAuctionsTable({ auctions, status }) {
  const rows = auctions?.recent ?? []
  if (!rows.length) {
    return (
      <section className="card card-pad" aria-label="Gilt auctions">
        <div className="label-xs">Gilt auctions</div>
        <p className="mt-2 text-xs text-muted">
          DMO auction results unavailable this run{status?.error ? ` (${status.error})` : ''}.
        </p>
      </section>
    )
  }
  return (
    <Table
      title="Conventional gilt auctions"
      subtitle="Recent DMO auction results. Higher cover and a smaller tail mean stronger demand."
      footer="Source: UK Debt Management Office. Index-linked auctions are excluded (real yields aren't comparable)."
    >
      <thead className="border-b border-hairline">
        <tr><Th>Auction</Th><Th right>Size</Th><Th right>Yield</Th><Th right>Cover</Th><Th right>Tail</Th></tr>
      </thead>
      <tbody>
        {rows.map((a) => (
          <tr key={`${a.date}-${a.name}`} className="border-b border-hairline/60 last:border-0">
            <Td className="text-ink">{dayShort(a.date)} · {a.name}</Td>
            <Td right className="text-muted">{a.size_bn ? `£${a.size_bn}bn` : '—'}</Td>
            <Td right className="text-ink">{a.yield !== null && a.yield !== undefined ? pct(a.yield, 3) : '—'}</Td>
            <Td right className="text-ink">{a.cover?.toFixed(2) ?? '—'}</Td>
            <Td right className="text-muted">{a.tail_bp !== null && a.tail_bp !== undefined ? `${a.tail_bp.toFixed(1)}bp` : '—'}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

export function NotesCard({ notes, className = '' }) {
  const items = notes ?? []
  return (
    <section className={`card card-pad flex min-h-0 flex-col ${className}`} aria-label="Dealer and client commentary">
      <div className="label-xs">Dealer / client commentary</div>
      {items.length ? (
        <ul className="mt-2.5 min-h-0 flex-1 space-y-2.5 overflow-y-auto pr-1 scroll-thin">
          {items.map((n, i) => (
            <li key={`${n.date}-${i}`} className="rounded-md border border-hairline px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2 text-[10px] text-faint">
                <span className="num">{dayLong(n.date)}</span><span>·</span><span>{n.source}</span>
                {(n.tags ?? []).map((t) => <span key={t} className="rounded border border-hairline px-1.5 py-px">{t}</span>)}
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-ink">{n.text}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2.5 flex-1 text-xs leading-relaxed text-muted">
          No notes yet. Add dealer and client commentary by hand to{' '}
          <code className="text-ink">config/notes.json</code> — it appears here on the next refresh.
        </p>
      )}
    </section>
  )
}

const SOURCE_LABELS = {
  'boe:gilt_curves': 'BoE gilt / real / inflation curves',
  'refinitiv:mpc_ois': 'Refinitiv MPC-dated OIS',
  'cftc:sterling': 'CFTC sterling positioning',
  'dmo:auctions': 'DMO gilt auctions',
}

export function RatesSourcesStatus({ status }) {
  if (!status) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {Object.entries(SOURCE_LABELS).map(([k, label]) => {
        const s = status[k]
        const ok = s?.ok
        const text = ok ? 'ok' : s?.error === 'no credentials configured' ? 'not configured' : 'stale'
        return (
          <span key={k} title={s?.error ?? ''} className={`rounded border px-2 py-0.5 ${ok ? 'border-hairline text-muted' : 'border-[#E9B872]/40 text-[#E9B872]'}`}>
            {label} · {text}
          </span>
        )
      })}
    </div>
  )
}
