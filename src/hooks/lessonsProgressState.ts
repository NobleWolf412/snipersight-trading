export interface LessonsProgressState {
    readChapterIds: string[];
    lastOpenedChapterId: string | null;
}
export function normalizeLessonsProgress(value: unknown, chapterIds: readonly string[]): LessonsProgressState {
    const state = value && typeof value === 'object' ? value as Partial<LessonsProgressState> : {};
    const known = new Set(chapterIds);
    return {
        readChapterIds: Array.isArray(state.readChapterIds)
            ? [...new Set(state.readChapterIds.filter(id => typeof id === 'string' && known.has(id)))] : [],
        lastOpenedChapterId: typeof state.lastOpenedChapterId === 'string' && known.has(state.lastOpenedChapterId)
            ? state.lastOpenedChapterId : null,
    };
}
