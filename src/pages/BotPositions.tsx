import { SectionHead } from '@/components/hud';
import type { BotPlaySelection } from '@/services/playInspector';
import { OPEN_POS_COLS, PENDING_ORDER_COLS, PendingOrderRow, PositionRow } from './BotStatusViews';
import type { buildBotStatusViewModel } from './botStatusViewModel';
type Model = ReturnType<typeof buildBotStatusViewModel>;
export function BotPositions({ positions, pendingOrders, onSelect }: Pick<Model, 'positions' | 'pendingOrders'> & {
    onSelect: (selection: BotPlaySelection) => void;
}) {
    return (<>          {/* ── Active Positions (filled + pending limit orders) ──── */}
          <section className="panel" style={{ padding: 14 }}>
            <SectionHead title="Active Positions" right={<span className="mono" style={{ fontSize: 10, color: 'var(--fg-4)' }}>
                  {positions.length} open · {pendingOrders.length} pending
                </span>}/>

            {/* Open subsection */}
            <div className="mono" style={{
            marginTop: 8,
            padding: '4px 12px',
            fontSize: 9,
            color: 'var(--fg-3)',
            letterSpacing: '.22em',
            textTransform: 'uppercase',
            borderBottom: '1px solid var(--border-soft)',
        }}>
              Open
            </div>
            {positions.length === 0 ? (<div className="mono" style={{
                padding: 14,
                textAlign: 'center',
                fontSize: 10,
                color: 'var(--fg-4)',
                letterSpacing: '.16em',
                textTransform: 'uppercase',
            }}>
                — no open positions —
              </div>) : (<div className="session-position-scroll" role="region" aria-label="Position prices and quantities" tabIndex={0}><div className="mono" style={{
                display: 'grid',
                gridTemplateColumns: OPEN_POS_COLS,
                gap: 10,
                padding: '8px 12px',
                fontSize: 9,
                color: 'var(--fg-4)',
                letterSpacing: '.18em',
                textTransform: 'uppercase',
            }}>
                  <span>Symbol</span>
                  <span>Side</span>
                  <span>Entry</span>
                  <span>Mark</span>
                  <span>Stop</span>
                  <span>Target</span>
                  <span style={{ textAlign: 'right' }}>uPnL</span>
                  <span style={{ textAlign: 'right' }}>R</span>
                </div>
                {positions.map((p) => (<PositionRow key={p.position_id} position={p} onClick={() => onSelect({ kind: 'position', id: p.position_id })}/>))}
              </div>)}

            {/* Pending subsection */}
            <div className="mono" style={{
            marginTop: 14,
            padding: '4px 12px',
            fontSize: 9,
            color: 'var(--fg-3)',
            letterSpacing: '.22em',
            textTransform: 'uppercase',
            borderBottom: '1px solid var(--border-soft)',
        }}>
              Pending (limit, awaiting fill)
            </div>
            {pendingOrders.length === 0 ? (<div className="mono" style={{
                padding: 14,
                textAlign: 'center',
                fontSize: 10,
                color: 'var(--fg-4)',
                letterSpacing: '.16em',
                textTransform: 'uppercase',
            }}>
                — none pending —
              </div>) : (<div className="session-position-scroll" role="region" aria-label="Position prices and quantities" tabIndex={0}><div className="mono" style={{
                display: 'grid',
                gridTemplateColumns: PENDING_ORDER_COLS,
                gap: 10,
                padding: '8px 12px',
                fontSize: 9,
                color: 'var(--fg-4)',
                letterSpacing: '.18em',
                textTransform: 'uppercase',
            }}>
                  <span>Symbol</span>
                  <span>Side</span>
                  <span>Limit</span>
                  <span>Qty</span>
                  <span style={{ textAlign: 'right' }}>Status</span>
                </div>
                {pendingOrders.map((o) => (<PendingOrderRow key={o.order_id} order={o} onClick={() => onSelect({ kind: 'pending', id: o.order_id })}/>))}
              </div>)}
          </section>

    </>);
}
