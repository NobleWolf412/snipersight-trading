import type { ReactNode } from 'react';

export function ChapterPara({ children }: { children: ReactNode }) {
  return (
    <p
      style={{
        margin: '0 0 14px',
        fontSize: 14,
        lineHeight: 1.65,
        color: 'var(--fg-1)',
      }}
    >
      {children}
    </p>
  );
}

export function ChapterSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section style={{ marginTop: 26 }}>
      <div
        className="mono"
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          letterSpacing: '.22em',
          textTransform: 'uppercase',
          marginBottom: 12,
          paddingBottom: 6,
          borderBottom: '1px dashed var(--border-soft)',
        }}
      >
        {title}
      </div>
      {children}
    </section>
  );
}

export function MistakeGrid({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: 12,
      }}
    >
      {children}
    </div>
  );
}

export function HeroWrap({
  children,
  caption,
}: {
  children: ReactNode;
  caption?: string;
}) {
  return (
    <div style={{ margin: '14px 0 6px' }}>
      {children}
      {caption && (
        <div
          className="mono"
          style={{
            fontSize: 10,
            color: 'var(--fg-4)',
            letterSpacing: '.14em',
            textAlign: 'center',
            marginTop: 4,
          }}
        >
          {caption}
        </div>
      )}
    </div>
  );
}
