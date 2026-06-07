import { useCallback, useMemo } from 'react';
import { useLocalStorage } from './useLocalStorage';

const STORAGE_KEY = 'sniper.lessons.v1';

interface LessonsProgressState {
  readChapterIds: string[];
  lastOpenedChapterId: string | null;
}

const DEFAULT_STATE: LessonsProgressState = {
  readChapterIds: [],
  lastOpenedChapterId: null,
};

interface ChapterRef {
  id: string;
  num: number;
  title: string;
}

export interface UseLessonsProgressResult<C extends ChapterRef> {
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
  const [state, setState] = useLocalStorage<LessonsProgressState>(
    STORAGE_KEY,
    DEFAULT_STATE,
  );

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
