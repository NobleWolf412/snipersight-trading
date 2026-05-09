// ActiveScanBeacon — Phase 7 sub-step 3 Tailwind eject.
// Replaced Tailwind utility classes with inline styles. The custom
// keyframe-driven classes (`beacon-pill-slide-in`, `beacon-glow-breathe`,
// `beacon-float`, `beacon-sonar-ring`, `beacon-radar-sweep`) live in
// `src/index.css` and survive the Tailwind ejection.
//
// `group-hover` was the only Tailwind feature with no direct inline
// equivalent — replaced with a local `hovered` state on the wrapping
// div so the arrow opacity + scale-on-hover behaviour preserves.

import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';

type ModeConfig = {
  label: string;
  shortCode: string;
  route: string;
  color: string;
  glow: string;
  ringColor: string;
};

const MODE_CONFIG: Record<string, ModeConfig> = {
  bot: {
    label: 'AUTONOMOUS BOT',
    shortCode: 'BOT',
    route: '/bot/status',
    color: '#f59e0b',
    glow: '0 0 30px rgba(245,158,11,0.8), 0 0 60px rgba(245,158,11,0.4), 0 0 100px rgba(245,158,11,0.2)',
    ringColor: 'rgba(245,158,11,',
  },
  training: {
    label: 'TRAINING GROUND',
    shortCode: 'TRN',
    route: '/training',
    color: '#00ff9d',
    glow: '0 0 30px rgba(0,255,157,0.8), 0 0 60px rgba(0,255,157,0.4), 0 0 100px rgba(0,255,157,0.2)',
    ringColor: 'rgba(0,255,157,',
  },
  scanner: {
    label: 'RECONNAISANCE',
    shortCode: 'RCN',
    route: '/scanner',
    color: '#22d3ee',
    glow: '0 0 30px rgba(34,211,238,0.8), 0 0 60px rgba(34,211,238,0.4), 0 0 100px rgba(34,211,238,0.2)',
    ringColor: 'rgba(34,211,238,',
  },
};

function SingleBeacon({ modeKey, onClick }: { modeKey: string; onClick: () => void }) {
  const [hovered, setHovered] = useState(false);
  const cfg = MODE_CONFIG[modeKey];
  const { color, glow, ringColor, label, shortCode } = cfg;

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={`Return to ${label}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
        cursor: 'pointer',
        userSelect: 'none',
      }}
    >
      {/* Label pill */}
      <div
        className="beacon-pill-slide-in"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 12px',
          borderRadius: '9999px',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.15em',
          border: `1px solid ${color}60`,
          backdropFilter: 'blur(4px)',
          whiteSpace: 'nowrap',
          color,
          backgroundColor: `${color}12`,
          boxShadow: `0 0 12px ${color}30`,
          textShadow: `0 0 8px ${color}`,
        }}
      >
        <span
          className="beacon-glow-breathe"
          style={{
            width: 6,
            height: 6,
            borderRadius: '9999px',
            display: 'inline-block',
            backgroundColor: color,
            boxShadow: `0 0 6px ${color}`,
          }}
        />
        {label}
        <span
          style={{
            opacity: hovered ? 1 : 0.6,
            transition: 'opacity 200ms',
            marginLeft: 4,
          }}
        >
          →
        </span>
      </div>

      {/* Beacon orb */}
      <div
        className="beacon-float"
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 68,
          height: 68,
        }}
      >
        {/* Sonar rings */}
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="beacon-sonar-ring"
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '9999px',
              border: `2px solid ${ringColor}0.7)`,
            }}
          />
        ))}

        {/* Radar sweep layer */}
        <div
          className="beacon-radar-sweep"
          style={{
            position: 'absolute',
            inset: 4,
            borderRadius: '9999px',
            background: `conic-gradient(from 0deg, ${color}90 0deg, ${color}30 55deg, transparent 90deg, transparent 360deg)`,
          }}
        />

        {/* Outer ring border */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '9999px',
            border: `2px solid ${color}80`,
            boxShadow: glow,
            transition: 'transform 300ms',
            transform: hovered ? 'scale(1.05)' : 'scale(1)',
          }}
        />

        {/* Inner dark core */}
        <div
          style={{
            position: 'relative',
            zIndex: 10,
            width: 44,
            height: 44,
            borderRadius: '9999px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'radial-gradient(circle, #0d0d0d 60%, #000 100%)',
            border: `1px solid ${color}40`,
          }}
        >
          {/* Short code */}
          <span
            style={{
              fontSize: 9,
              fontWeight: 900,
              letterSpacing: '0.2em',
              color,
              textShadow: `0 0 8px ${color}`,
            }}
          >
            {shortCode}
          </span>

          {/* Tiny live dot */}
          <span
            className="beacon-glow-breathe"
            style={{
              width: 4,
              height: 4,
              borderRadius: '9999px',
              marginTop: 2,
              backgroundColor: color,
              boxShadow: `0 0 4px ${color}`,
            }}
          />
        </div>
      </div>
    </div>
  );
}

export function ActiveScanBeacon() {
  const { isTrainingActive, isScanning, isBotActive } = useScanner();
  const navigate = useNavigate();
  const location = useLocation();

  // Ordered by priority — Bot first, then Training, then Scanner
  const activeModes: string[] = [];
  if (isBotActive) activeModes.push('bot');
  if (isTrainingActive) activeModes.push('training');
  if (isScanning) activeModes.push('scanner');

  // Never show the beacon on the page that's already active
  const filtered = activeModes.filter((key) => {
    const cfg = MODE_CONFIG[key];
    return !location.pathname.startsWith(cfg.route.split('/').slice(0, 3).join('/'));
  });

  if (filtered.length === 0) return null;

  // Show primary beacon (highest priority), with a +N badge if others are also running
  const primary = filtered[0];
  const extras = filtered.length - 1;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 90,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 16,
        pointerEvents: 'auto',
      }}
    >
      {extras > 0 && (
        <div
          style={{
            alignSelf: 'flex-end',
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: '0.1em',
            padding: '2px 8px',
            borderRadius: '9999px',
            border: `1px solid ${MODE_CONFIG[filtered[1]].color}40`,
            color: MODE_CONFIG[filtered[1]].color,
            backgroundColor: `${MODE_CONFIG[filtered[1]].color}10`,
          }}
        >
          +{extras} MORE ACTIVE
        </div>
      )}

      <SingleBeacon
        modeKey={primary}
        onClick={() => navigate(MODE_CONFIG[primary].route)}
      />
    </div>
  );
}
