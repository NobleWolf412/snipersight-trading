// SniperReticle — Phase 7 sub-step 3 Tailwind eject.
// Replaced Tailwind utilities with inline styles using HUD CSS variables
// so the component survives the Tailwind removal in Phase 7 sub-step 5.
// Custom classes `scope-reticle` and `scope-marker` continue to live in
// `src/styles/hud-effects.css` and are unaffected.
//
// Color: --destructive (oklch red) for the crosshair core; the HUD red
// shadow (rgba 255,0,0,0.5) preserved verbatim from the previous
// `shadow-[0_0_4px_rgba(255,0,0,0.5)]` utility for visual parity.

import { Crosshair } from '@phosphor-icons/react';
import { useMousePosition } from '@/hooks/useMousePosition';

const RED = 'var(--destructive)';
const RED_30 = 'color-mix(in oklch, var(--destructive) 30%, transparent)';
const RED_60 = 'color-mix(in oklch, var(--destructive) 60%, transparent)';
const RED_80 = 'color-mix(in oklch, var(--destructive) 80%, transparent)';
const TICK_SHADOW = '0 0 4px rgba(255,0,0,0.5)';

export function SniperReticle() {
  const mousePosition = useMousePosition();

  return (
    <div
      className="scope-reticle"
      style={{
        position: 'fixed',
        pointerEvents: 'none',
        zIndex: 100,
        willChange: 'transform',
        left: `${mousePosition.x}px`,
        top: `${mousePosition.y}px`,
        transform: 'translate(-50%, -50%)',
      }}
    >
      <div style={{ position: 'relative' }}>
        <Crosshair size={40} weight="regular" style={{ color: RED }} />

        {/* simplified pulse to reduce layout thrash */}
        <div
          className="scope-marker"
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              border: `1px solid ${RED_30}`,
              borderRadius: '9999px',
            }}
          />
        </div>

        {/* outer dashed halo */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              width: 56,
              height: 56,
              border: `1px dashed ${RED_30}`,
              borderRadius: '9999px',
            }}
          />
        </div>

        {/* center dot */}
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
          }}
        >
          <div
            style={{
              width: 4,
              height: 4,
              background: RED,
              borderRadius: '9999px',
            }}
          />
        </div>

        {/* top tick */}
        <div
          className="scope-marker"
          style={{
            position: 'absolute',
            left: '50%',
            top: 0,
            transform: 'translate(-50%, -32px)',
          }}
        >
          <div
            style={{
              height: 24,
              width: 1,
              background: RED_60,
              boxShadow: TICK_SHADOW,
            }}
          />
        </div>

        {/* bottom tick */}
        <div
          className="scope-marker"
          style={{
            position: 'absolute',
            left: '50%',
            bottom: 0,
            transform: 'translate(-50%, 32px)',
          }}
        >
          <div
            style={{
              height: 24,
              width: 1,
              background: RED_60,
              boxShadow: TICK_SHADOW,
            }}
          />
        </div>

        {/* left tick */}
        <div
          className="scope-marker"
          style={{
            position: 'absolute',
            top: '50%',
            left: 0,
            transform: 'translate(-32px, -50%)',
          }}
        >
          <div
            style={{
              width: 24,
              height: 1,
              background: RED_60,
              boxShadow: TICK_SHADOW,
            }}
          />
        </div>

        {/* right tick */}
        <div
          className="scope-marker"
          style={{
            position: 'absolute',
            top: '50%',
            right: 0,
            transform: 'translate(32px, -50%)',
          }}
        >
          <div
            style={{
              width: 24,
              height: 1,
              background: RED_60,
              boxShadow: TICK_SHADOW,
            }}
          />
        </div>

        {/* coords readout */}
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            marginTop: 24,
            fontSize: 10,
            fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, monospace',
            color: RED_80,
            whiteSpace: 'nowrap',
            letterSpacing: '0.1em',
          }}
        >
          X:{Math.round(mousePosition.x)} Y:{Math.round(mousePosition.y)}
        </div>
      </div>
    </div>
  );
}
