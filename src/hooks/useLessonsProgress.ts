import { useCallback,useEffect,useMemo,useState } from 'react';
import { normalizeLessonsProgress,type LessonsProgressState } from './lessonsProgressState';
const STORAGE_KEY = 'sniper.lessons.v1';
const DEFAULT_STATE: LessonsProgressState = { readChapterIds: [], lastOpenedChapterId: null };

interface ChapterRef {
  id: string;
  num: number;
  title: string;
}

export interface UseLessonsProgressResult<C extends ChapterRef> {
  persistenceError: string | null;
  readChapterIds: string[];
  lastOpenedChapterId: string | null;
  markRead: (id: string) => void;
  markUnread: (id: string) => void;
  toggleRead: (id: string) => void;
  setLastOpened: (id: string) => void;
  reset: () => void;
  counts: {
    done: number;
    total: number;
    nextChapter: C | null;
    pct: number;
  };
}

export function useLessonsProgress<C extends ChapterRef>(
  chapters: C[],
): UseLessonsProgressResult<C> {
  const [persistenceError, setPersistenceError] = useState<string | null>(null);
  const [state, setState] = useState<LessonsProgressState>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return normalizeLessonsProgress(raw ? JSON.parse(raw) : DEFAULT_STATE, chapters.map(chapter => chapter.id));
    } catch { return DEFAULT_STATE; }
  });
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); setPersistenceError(null); }
    catch { setPersistenceError('Progress cannot be saved in this browser. It is kept only for this visit.'); }
  }, [state]);

  const markRead = useCallback(
    (id: string) =>
      setState((prev) =>
        prev.readChapterIds.includes(id)
          ? prev
          : { ...prev, readChapterIds: [...prev.readChapterIds, id] },
      ),
    [setState],
  );

  const markUnread = useCallback(
    (id: string) =>
      setState((prev) => ({
        ...prev,
        readChapterIds: prev.readChapterIds.filter((x) => x !== id),
      })),
    [setState],
  );

  const toggleRead = useCallback(
    (id: string) =>
      setState((prev) => ({
        ...prev,
        readChapterIds: prev.readChapterIds.includes(id)
          ? prev.readChapterIds.filter((x) => x !== id)
          : [...prev.readChapterIds, id],
      })),
    [setState],
  );

  const setLastOpened = useCallback(
    (id: string) =>
      setState((prev) =>
        prev.lastOpenedChapterId === id
          ? prev
          : { ...prev, lastOpenedChapterId: id },
      ),
    [setState],
  );

  const reset = useCallback(() => setState(DEFAULT_STATE), [setState]);

  const counts = useMemo(() => {
    const total = chapters.length;
    const done = chapters.filter((c) => state.readChapterIds.includes(c.id))
      .length;
    const nextChapter =
      chapters.find((c) => !state.readChapterIds.includes(c.id)) ?? null;
    const pct = total ? Math.round((done / total) * 100) : 0;
    return { done, total, nextChapter, pct };
  }, [chapters, state.readChapterIds]);

  return {
    persistenceError,
    readChapterIds: state.readChapterIds,
    lastOpenedChapterId: state.lastOpenedChapterId,
    markRead,
    markUnread,
    toggleRead,
    setLastOpened,
    reset,
    counts,
  };
}
