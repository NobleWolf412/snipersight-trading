// HUD Reticle — rotating SVG overlay for accent panels.
// Port of prototype/shared.jsx Reticle.

export function Reticle() {
  return (
    <div className="reticle">
      <svg viewBox="-100 -100 200 200" fill="none">
        <g className="ring-rotate">
          <circle r="80" stroke="currentColor" strokeOpacity=".35" strokeWidth=".4" strokeDasharray="2 4" />
          <line x1="-90" y1="0" x2="-72" y2="0" stroke="currentColor" strokeOpacity=".5" strokeWidth=".6" />
          <line x1="72" y1="0" x2="90" y2="0" stroke="currentColor" strokeOpacity=".5" strokeWidth=".6" />
        </g>
        <g className="ring-rotate-rev">
          <circle r="55" stroke="currentColor" strokeOpacity=".5" strokeWidth=".5" />
          <line y1="-65" x1="0" y2="-48" x2="0" stroke="currentColor" strokeOpacity=".6" strokeWidth=".8" />
          <line y1="48" x1="0" y2="65" x2="0" stroke="currentColor" strokeOpacity=".6" strokeWidth=".8" />
        </g>
        <circle r="3" fill="currentColor" />
        <circle r="22" stroke="currentColor" strokeOpacity=".4" strokeWidth=".5" />
      </svg>
    </div>
  );
}
