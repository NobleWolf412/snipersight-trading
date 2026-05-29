import { useEffect, useState, type ReactNode } from 'react';

const STORAGE_PREFIX = 'sniper.lessons.flipcard.';

export interface FlipCardProps {
  front: ReactNode;
  back: ReactNode;
  localStorageKey?: string;
  height?: number;
  frontAccent?: string;
  backAccent?: string;
}

export function FlipCard({
  front,
  back,
  localStorageKey,
  height = 180,
  frontAccent = '#22d3ee',
  backAccent = '#fbbf24',
}: FlipCardProps) {
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    if (!localStorageKey || !flipped) return;
    try {
      localStorage.setItem(STORAGE_PREFIX + localStorageKey, '1');
    } catch {
      // localStorage may be unavailable (private mode, etc.) — viewed-state
      // tracking is non-critical, swallow.
    }
  }, [flipped, localStorageKey]);

  return (
    <div
      onClick={() => setFlipped((f) => !f)}
      role="button"
      tabIndex={0}
      aria-pressed={flipped}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          setFlipped((f) => !f);
        }
      }}
      style={{
        perspective: 1200,
        cursor: 'pointer',
        height,
        outline: 'none',
      }}
    >
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          transformStyle: 'preserve-3d',
          transition: 'transform .55s cubic-bezier(.4,.0,.2,1)',
          transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
        }}
      >
        <FlipFace accent={frontAccent} hintLabel="TAP TO FLIP →">
          {front}
        </FlipFace>
        <FlipFace accent={backAccent} hintLabel="← TAP TO FLIP BACK" back>
          {back}
        </FlipFace>
      </div>
    </div>
  );
}

interface FlipFaceProps {
  accent: string;
  hintLabel: string;
  back?: boolean;
  children: ReactNode;
}

function FlipFace({ accent, hintLabel, back, children }: FlipFaceProps) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backfaceVisibility: 'hidden',
        transform: back ? 'rotateY(180deg)' : undefined,
        padding: '16px 18px',
        border: `1px solid ${accent}`,
        borderRadius: 8,
        background: 'rgba(0,0,0,.45)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        boxShadow: `0 0 0 1px ${accent}22, 0 4px 18px rgba(0,0,0,.4)`,
      }}
    >
      <div
        style={{
          fontFamily: 'JetBrains Mono,monospace',
          fontSize: 13,
          color: 'var(--fg)',
          lineHeight: 1.5,
        }}
      >
        {children}
      </div>
      <div
        className="mono"
        style={{
          fontSize: 9,
          color: accent,
          letterSpacing: '.2em',
          textAlign: 'right',
          marginTop: 8,
        }}
      >
        {hintLabel}
      </div>
    </div>
  );
}
