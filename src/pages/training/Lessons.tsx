import { FooterStatus,PageHead } from '@/components/hud';
import { ChapterShell } from '@/components/lessons/primitives';
import { CHAPTERS } from '@/content/lessons';
import { useLessonsProgress } from '@/hooks/useLessonsProgress';
import { Suspense,useEffect } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { Link,useLocation } from 'react-router-dom';
import './Lessons.css';

export function Lessons() {
  const { hash } = useLocation();
  const progress = useLessonsProgress(CHAPTERS);
  const id = hash.startsWith('#ch-') ? hash.slice(4) : null;
  const chapter = CHAPTERS.find(item => item.id === id);
  const { setLastOpened } = progress;
  useEffect(() => { if (chapter) setLastOpened(chapter.id); }, [chapter, setLastOpened]);
  const index = chapter ? CHAPTERS.indexOf(chapter) : -1;
  const resume = CHAPTERS.find(item => item.id === progress.lastOpenedChapterId) ?? progress.counts.nextChapter ?? CHAPTERS[0];
  const notice = <p className="lesson-reference-notice">Educational reference with illustrative and historical examples.
    Active mode requirements and evidence policy are shown in the scanner.
    Chapter examples are not current signals, risk settings or performance guarantees.</p>;
  if (chapter) {
    const Body = chapter.Body;
    return <ChapterShell chapter={chapter} allChapters={CHAPTERS}
      isRead={progress.readChapterIds.includes(chapter.id)} onToggleRead={() => progress.toggleRead(chapter.id)}
      sources={chapter.sources} prev={CHAPTERS[index - 1]} next={CHAPTERS[index + 1]}
      progressCounts={progress.counts}>
      <Link className="btn" to="/training/lessons">Chapter library</Link>
      {progress.persistenceError && <p role="alert">{progress.persistenceError}</p>}
    {notice}
      <ErrorBoundary resetKeys={[chapter.id]} fallbackRender={({ resetErrorBoundary }) =>
        <div role="alert"><p>Chapter content could not load.</p><button className="btn" onClick={resetErrorBoundary}>Retry chapter</button></div>}>
        <Suspense fallback={<p role="status">Loading chapter…</p>}><Body /></Suspense>
      </ErrorBoundary>
    </ChapterShell>;
  }
  return <div className="page lesson-library">
    <PageHead title="Lessons" subtitle="Read and resume strategy chapters" />
    {id && <p role="alert">That chapter is unavailable. Choose a chapter below.</p>}
    <Link className="btn btn-cyan" to={`/training/lessons#ch-${resume.id}`}>Resume: {resume.title}</Link>
    <p>{progress.counts.done} of {progress.counts.total} chapters marked read. Progress belongs to this browser.</p>
    {progress.persistenceError && <p role="alert">{progress.persistenceError}</p>}
    {notice}
    <ol className="lesson-library__chapters">
      {CHAPTERS.map(item => <li key={item.id}><Link to={`/training/lessons#ch-${item.id}`}>
        <h2>{item.title}</h2><p>{item.summary}</p>
        <span className="mono">{progress.readChapterIds.includes(item.id) ? 'READ' : 'UNREAD'}</span>
      </Link></li>)}
    </ol>
    <FooterStatus />
  </div>;
}
