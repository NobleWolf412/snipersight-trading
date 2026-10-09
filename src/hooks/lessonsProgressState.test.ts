import { describe, expect, it } from 'vitest';
import { normalizeLessonsProgress } from './lessonsProgressState';
describe('lesson progress recovery', () => {
    it('recovers malformed persisted data and drops retired chapter IDs', () => {
        expect(normalizeLessonsProgress(null, ['a'])).toEqual({ readChapterIds: [], lastOpenedChapterId: null });
        expect(normalizeLessonsProgress({ readChapterIds: 'a', lastOpenedChapterId: 3 }, ['a']).readChapterIds).toEqual([]);
        expect(normalizeLessonsProgress({ readChapterIds: ['a', 'a', 'old', 3], lastOpenedChapterId: 'old' }, ['a']))
            .toEqual({ readChapterIds: ['a'], lastOpenedChapterId: null });
    });
});
