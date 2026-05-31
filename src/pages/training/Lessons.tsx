/**
 * Lessons — strategy library (scaffold)
 *
 * Content lives under src/content/lessons/. This stub unblocks navigation
 * from Training Ground so chapter pages can be iterated in-place.
 */
import { useEffect, useRef } from 'react';
import { Chip, FooterStatus, PageHead } from '@/components/hud';

export function Lessons() {
  const readyRef = useRef(false);

  useEffect(() => {
    if (!readyRef.current) {
      readyRef.current = true;
      document.body.setAttribute('data-snapshot-ready', 'true');
    }
    return () => {
      document.body.removeAttribute('data-snapshot-ready');
    };
  }, []);

  return (
    <div className="page">
      <PageHead
        icon={
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 5 L12 3 L20 5 L20 19 L12 17 L4 19 Z"
              stroke="currentColor"
              strokeWidth="1.5"
              fill="none"
              style={{ color: '#4ade80' }}
            />
            <line
              x1="12"
              y1="3"
              x2="12"
              y2="17"
              stroke="currentColor"
              strokeWidth="1"
              style={{ color: '#4ade80' }}
            />
          </svg>
        }
        title="Lessons"
        subtitle="Strategy library — order blocks, FVGs, liquidity sweeps, regime detection, position sizing"
        badges={
          <>
            <Chip kind="green">● SCAFFOLD</Chip>
            <Chip kind="cyan">CHAPTERS · 0</Chip>
          </>
        }
      />

      <div
        className="panel"
        style={{
          padding: 32,
          textAlign: 'center',
          color: 'var(--fg-3)',
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: 13,
          letterSpacing: '.16em',
          margin: '24px 0',
        }}
      >
        LESSONS UI · IN DEVELOPMENT
        <div
          style={{
            marginTop: 12,
            fontSize: 11,
            color: 'var(--fg-4)',
            letterSpacing: '.12em',
          }}
        >
          Chapter content lives under src/content/lessons/
        </div>
      </div>

      <FooterStatus latency={36} />
    </div>
  );
}

export default Lessons;
