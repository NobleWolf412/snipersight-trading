// HUD FooterStatus — bottom status strip.
// Connection and source status are shown by their owning feed/session panels.
export function FooterStatus() {
  const now = Date.now();
  const ts = new Date(now).toISOString().slice(0, 19).replace('T', ' ') + 'Z';
  return (
    <div
      style={{
        marginTop: 24,
        padding: '12px 18px',
        border: '1px solid var(--border-soft)',
        borderRadius: 10,
        background: 'rgba(0,0,0,.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 14,
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        Market category data: <a href="https://www.coingecko.com" target="_blank" rel="noopener noreferrer">CoinGecko</a>
      </div>
      <div
        className="mono"
        style={{
          fontSize: 10,
          color: 'var(--fg-4)',
          letterSpacing: '.18em',
          textTransform: 'uppercase',
        }}
      >
        Rendered {ts}
      </div>
    </div>
  );
}
