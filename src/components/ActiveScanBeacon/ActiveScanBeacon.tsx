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
    route: '/scanner/status',
    color: '#22d3ee',
    glow: '0 0 30px rgba(34,211,238,0.8), 0 0 60px rgba(34,211,238,0.4), 0 0 100px rgba(34,211,238,0.2)',
    ringColor: 'rgba(34,211,238,',
  },
};

function SingleBeacon({ modeKey, onClick }: { modeKey: string; onClick: () => void }) {
  const cfg = MODE_CONFIG[modeKey];
  const { color, glow, ringColor, label, shortCode } = cfg;

  return (
    <div
      className="flex flex-col items-center gap-2 cursor-pointer group select-none"
      onClick={onClick}
      title={`Return to ${label}`}
    >
      {/* Label pill */}
      <div
        className="beacon-pill-slide-in flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold tracking-[0.15em] border backdrop-blur-sm whitespace-nowrap"
        style={{
          color,
          borderColor: `${color}60`,
          backgroundColor: `${color}12`,
          boxShadow: `0 0 12px ${color}30`,
          textShadow: `0 0 8px ${color}`,
        }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full beacon-glow-breathe inline-block"
          style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
        />
        {label}
        <span className="opacity-60 group-hover:opacity-100 transition-opacity ml-1">→</span>
      </div>

      {/* Beacon orb */}
      <div className="relative flex items-center justify-center beacon-float" style={{ width: 68, height: 68 }}>

        {/* Sonar rings */}
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="beacon-sonar-ring absolute inset-0 rounded-full border-2"
            style={{ borderColor: `${ringColor}0.7)` }}
          />
        ))}

        {/* Radar sweep layer */}
        <div
          className="beacon-radar-sweep absolute rounded-full"
          style={{
            inset: 4,
            background: `conic-gradient(from 0deg, ${color}90 0deg, ${color}30 55deg, transparent 90deg, transparent 360deg)`,
          }}
        />

        {/* Outer ring border */}
        <div
          className="absolute inset-0 rounded-full border-2 transition-all duration-300 group-hover:scale-105"
          style={{
            borderColor: `${color}80`,
            boxShadow: glow,
          }}
        />

        {/* Inner dark core */}
        <div
          className="relative z-10 rounded-full flex flex-col items-center justify-center"
          style={{
            width: 44,
            height: 44,
            background: 'radial-gradient(circle, #0d0d0d 60%, #000 100%)',
            border: `1px solid ${color}40`,
          }}
        >
          {/* Short code */}
          <span
            className="text-[9px] font-black tracking-[0.2em]"
            style={{ color, textShadow: `0 0 8px ${color}` }}
          >
            {shortCode}
          </span>

          {/* Tiny live dot */}
          <span
            className="w-1 h-1 rounded-full mt-0.5 beacon-glow-breathe"
            style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }}
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
  const filtered = activeModes.filter(key => {
    const cfg = MODE_CONFIG[key];
    return !location.pathname.startsWith(cfg.route.split('/').slice(0, 3).join('/'));
  });

  if (filtered.length === 0) return null;

  // Show primary beacon (highest priority), with a +N badge if others are also running
  const primary = filtered[0];
  const extras = filtered.length - 1;

  return (
    <div
      className="fixed bottom-6 right-6 z-[90] flex flex-col items-center gap-4"
      style={{ pointerEvents: 'auto' }}
    >
      {extras > 0 && (
        <div
          className="self-end text-[9px] font-bold tracking-widest px-2 py-0.5 rounded-full border"
          style={{
            color: MODE_CONFIG[filtered[1]].color,
            borderColor: `${MODE_CONFIG[filtered[1]].color}40`,
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
