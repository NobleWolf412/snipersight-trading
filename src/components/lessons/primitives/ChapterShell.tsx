import { useEffect, useRef, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Chip, FooterStatus, PageHead, Reticle, SectionHead } from '@/components/hud';
import { SourceList } from './SourceList';
import type { ChapterMeta, SourceRef } from './types';

export interface ChapterShellProps {
  chapter: ChapterMeta;
  allChapters: ChapterMeta[];
  isRead: boolean;
  onToggleRead: () => void;
  sources: SourceRef[];
  prev?: ChapterMeta;
  next?: ChapterMeta;
  progressCounts: { done: number; total: number };
  children: ReactNode;
}

export function ChapterShell({
  chapter,
  allChapters,
  isRead,
  onToggleRead,
  sources,
  prev,
  next,
  progressCounts,
  children,
}: ChapterShellProps) {
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

  const pct = progressCounts.total
    ? Math.round((progressCounts.done / progressCounts.total) * 100)
    : 0;

  return (
    <div className="page">
      <PageHead
        title={`Ch ${chapter.num} · ${chapter.title}`}
        subtitle={chapter.summary}
        badges={
          <>
            <Chip kind="green">
              {progressCounts.done}/{progressCounts.total} READ · {pct}%
            </Chip>
            <Chip kind={isRead ? 'green' : undefined}>
              {isRead ? '● THIS CHAPTER READ' : '○ UNREAD'}
            </Chip>
          </>
        }
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '280px 1fr',
          gap: 18,
          marginTop: 14,
          alignItems: 'start',
        }}
        className="lessons-layout"
      >
        <ChapterNav
          allChapters={allChapters}
          activeId={chapter.id}
          progressCounts={progressCounts}
        />

        <section
          className="panel panel-accent"
          style={{ position: 'relative', overflow: 'hidden' }}
        >
          <Reticle />
          <div className="corner-tag tl">// LESSON {chapter.num.toString().padStart(2, '0')}</div>
          <div className="corner-tag tr" style={{ color: chapter.color }}>
            {isRead ? '● READ' : '○ UNREAD'}
          </div>
          <SectionHead
            title={chapter.title.toUpperCase()}
            right={
              <button
                type="button"
                onClick={onToggleRead}
                className="btn"
                style={{
                  fontSize: 10,
                  padding: '6px 12px',
                  letterSpacing: '.18em',
                  color: isRead ? 'var(--fg-4)' : chapter.color,
                  borderColor: isRead ? 'var(--border-soft)' : chapter.color,
                }}
              >
                {isRead ? '↺ MARK UNREAD' : '✓ MARK READ'}
              </button>
            }
          />
          <div style={{ padding: '18px 22px', color: 'var(--fg-1)', lineHeight: 1.6 }}>
            {children}
            <SourceList sources={sources} />
            <ChapterNavFooter prev={prev} next={next} accentColor={chapter.color} />
          </div>
        </section>
      </div>

      <FooterStatus latency={36} />

      <style>{`
        @media (max-width: 900px) {
          .lessons-layout {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}

interface ChapterNavProps {
  allChapters: ChapterMeta[];
  activeId: string;
  progressCounts: { done: number; total: number };
}

function ChapterNav({ allChapters, activeId, progressCounts }: ChapterNavProps) {
  return (
    <nav
      className="panel"
      aria-label="Lessons chapter navigation"
      style={{ padding: '12px 4px', position: 'sticky', top: 12 }}
    >
      <div
        className="mono"
        style={{
          fontSize: 9,
          color: 'var(--fg-4)',
          letterSpacing: '.24em',
          textTransform: 'uppercase',
          padding: '4px 14px 10px',
        }}
      >
        // CHAPTERS · {progressCounts.done}/{progressCounts.total}
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {allChapters.map((c) => {
          const isActive = c.id === activeId;
          return (
            <li key={c.id}>
              <Link
                to={`/training/lessons#ch-${c.id}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 14px',
                  textDecoration: 'none',
                  color: isActive ? c.color : 'var(--fg-2)',
                  background: isActive ? `${c.color}14` : 'transparent',
                  borderLeft: isActive ? `2px solid ${c.color}` : '2px solid transparent',
                  fontFamily: 'JetBrains Mono,monospace',
                  fontSize: 12,
                  letterSpacing: '.04em',
                  transition: 'background .15s, color .15s',
                }}
              >
                <span
                  className="mono"
                  style={{
                    fontSize: 10,
                    color: isActive ? c.color : 'var(--fg-4)',
                    minWidth: 18,
                    fontWeight: 700,
                  }}
                >
                  {c.num.toString().padStart(2, '0')}
                </span>
                <span style={{ flex: 1 }}>{c.title}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

interface ChapterNavFooterProps {
  prev?: ChapterMeta;
  next?: ChapterMeta;
  accentColor: string;
}

function ChapterNavFooter({ prev, next, accentColor }: ChapterNavFooterProps) {
  if (!prev && !next) return null;
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 22,
        paddingTop: 14,
        borderTop: '1px dashed var(--border-soft)',
        gap: 12,
      }}
    >
      {prev ? (
        <Link
          to={`/training/lessons#ch-${prev.id}`}
          className="mono"
          style={{
            fontSize: 11,
            color: 'var(--fg-3)',
            textDecoration: 'none',
            letterSpacing: '.14em',
          }}
        >
          ← CH {prev.num.toString().padStart(2, '0')} · {prev.title}
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link
          to={`/training/lessons#ch-${next.id}`}
          className="mono"
          style={{
            fontSize: 11,
            color: accentColor,
            textDecoration: 'none',
            letterSpacing: '.14em',
          }}
        >
          CH {next.num.toString().padStart(2, '0')} · {next.title} →
        </Link>
      ) : (
        <span />
      )}
    </div>
  );
}
