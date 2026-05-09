// Error boundary fallback. Originally used shadcn Alert/Button primitives;
// rewrote with vanilla HUD-themed markup in Phase 6 sub-step 4b after the
// shadcn ui/ tree was archived.
interface ErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
}

export const ErrorFallback = ({ error, resetErrorBoundary }: ErrorFallbackProps) => {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
        background: 'var(--bg, #0a0a0a)',
        color: 'var(--fg, #e6e6e6)',
        fontFamily: 'var(--font-mono, ui-monospace, monospace)',
      }}
    >
      <div style={{ width: '100%', maxWidth: 480 }}>
        <div
          className="panel"
          style={{
            padding: '1rem',
            marginBottom: '1.5rem',
            borderColor: 'var(--red, #ff5577)',
          }}
        >
          <div
            style={{
              fontSize: 12,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: 'var(--red, #ff5577)',
              marginBottom: 6,
            }}
          >
            // RUNTIME FAULT
          </div>
          <div style={{ fontSize: 14, lineHeight: 1.5 }}>
            The HUD encountered a runtime error. Details below. Reload to retry.
          </div>
        </div>

        <div
          className="panel"
          style={{
            padding: '0.75rem 1rem',
            marginBottom: '1.5rem',
          }}
        >
          <div
            style={{
              fontSize: 11,
              opacity: 0.6,
              marginBottom: 6,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
            }}
          >
            error.message
          </div>
          <pre
            style={{
              margin: 0,
              fontSize: 12,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              maxHeight: 160,
              overflow: 'auto',
              color: 'var(--red, #ff5577)',
            }}
          >
            {error.message}
          </pre>
        </div>

        <button
          type="button"
          className="btn btn-cyan"
          onClick={resetErrorBoundary}
          style={{ width: '100%' }}
        >
          ↻ retry
        </button>
      </div>
    </div>
  );
};
