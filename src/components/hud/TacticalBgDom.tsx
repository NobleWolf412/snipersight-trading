// HUD TacticalBgDom — tactical background layers (drift glow, grid, scanline, grain).
// Port of prototype/shared.jsx TacticalBgDom.
// Mounts as a fixed-position layer behind page content.

export function TacticalBgDom() {
  return (
    <div className="tactical-bg" id="tactical-bg">
      <div className="glow" />
      <div className="grid" />
      <div className="grain" />
      <div className="scanline" />
    </div>
  );
}
