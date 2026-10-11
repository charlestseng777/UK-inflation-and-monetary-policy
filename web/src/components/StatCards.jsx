import { PALETTE } from '../lib/series.js'
import { deltaArrow, deltaTone, monthLong, pct, pp } from '../lib/format.js'

const CARDS = [
  { id: 'headline_cpi', label: 'Headline CPI', color: PALETTE.headline, note: 'Target variable' },
  { id: 'core_cpi', label: 'Core CPI', color: PALETTE.core, note: 'Excl. energy, food, alcohol & tobacco' },
  { id: 'services_cpi', label: 'Services CPI', color: PALETTE.services, note: 'Domestic price pressure' },
  // Orange rather than wage growth's chart violet, which Core CPI already uses in this row.
  { id: 'wage_growth', label: 'Wage growth', color: PALETTE.policy, note: 'AWE regular pay, 3m y/y' },
]

/** Newest row with a value for `key`. Wages are published about a month after CPI, so their latest month can lag. */
export function lastWith(rows, key) {
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    if (rows[i][key] !== null && rows[i][key] !== undefined) return rows[i]
  }
  return null
}

export default function StatCards({ rows }) {
  if (!rows?.length) return null

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {CARDS.map((card) => {
        const row = lastWith(rows, card.id)
        const value = row?.[card.id]
        const change = row?.mom?.[card.id]
        return (
          <div key={card.id} className="card card-pad animate-fade-up">
            <div className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ backgroundColor: card.color }}
                aria-hidden="true"
              />
              <span className="label-xs">{card.label}</span>
            </div>

            <div className="mt-2 flex items-baseline gap-2">
              <span className="num text-3xl font-semibold leading-none text-ink">
                {value === null || value === undefined ? '—' : value.toFixed(2)}
              </span>
              <span className="text-base text-faint">%</span>
            </div>

            <div className={`mt-2 flex items-center gap-1.5 text-xs ${deltaTone(change)}`}>
              <span aria-hidden="true">{deltaArrow(change)}</span>
              <span className="num">{pp(change)}</span>
              <span className="text-faint">on the month</span>
            </div>

            <div className="mt-1.5 text-[11px] leading-snug text-faint">{card.note} · {monthLong(row?.date)}</div>
          </div>
        )
      })}
    </div>
  )
}

export function LatestSummary({ row, wage, realRate }) {
  if (!row) return null
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted">
      <span>
        Latest observation{' '}
        <span className="num text-ink">{monthLong(row.date)}</span>
      </span>
      <span>
        Real policy rate{' '}
        <span className="num text-ink">{pp(realRate)}</span>
      </span>
      {wage !== null && wage !== undefined && (
        <span>
          Regular pay growth{' '}
          <span className="num text-ink">{pct(wage)}</span>
        </span>
      )}
    </div>
  )
}
