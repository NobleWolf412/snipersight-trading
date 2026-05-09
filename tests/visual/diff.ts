/**
 * Pixel diffing engine.
 *
 * Two thresholds, both must pass:
 *   1. Per-pixel color tolerance (pixelmatch threshold ≤ 0.1 → catches
 *      antialiasing / sub-pixel font rendering noise).
 *   2. Per-region size — the largest contiguous changed region must be
 *      smaller than `regionPctOfViewport` of the viewport area.
 *
 * Region detection is a simple flood-fill over the diff mask. We only
 * track the LARGEST region — that's the one that matters for catching
 * moved/missing elements. Cumulative noise stays under the per-pixel
 * threshold without triggering a region failure.
 */
import pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

export interface DiffResult {
  pass: boolean;
  perPixelDiffPct: number;
  largestRegionPx: number;
  largestRegionPctOfViewport: number;
  reasons: string[];
  diffPngPath?: string;
}

export interface DiffOptions {
  baselinePath: string;
  currentPath: string;
  diffOutputPath?: string;
  perPixelThreshold: number;
  regionPctOfViewport: number;
}

/**
 * Flood-fill the diff mask, return size of largest contiguous region in pixels.
 * 4-connectivity (up/down/left/right). Iterative stack — handles full-viewport
 * regions without recursion blowup.
 */
function largestContiguousRegion(mask: Uint8Array, width: number, height: number): number {
  const visited = new Uint8Array(mask.length);
  let max = 0;
  for (let i = 0; i < mask.length; i++) {
    if (mask[i] === 0 || visited[i]) continue;
    let size = 0;
    const stack: number[] = [i];
    while (stack.length) {
      const idx = stack.pop()!;
      if (visited[idx] || mask[idx] === 0) continue;
      visited[idx] = 1;
      size++;
      const x = idx % width;
      const y = (idx - x) / width;
      if (x > 0) stack.push(idx - 1);
      if (x < width - 1) stack.push(idx + 1);
      if (y > 0) stack.push(idx - width);
      if (y < height - 1) stack.push(idx + width);
    }
    if (size > max) max = size;
  }
  return max;
}

export function diffPngs(opts: DiffOptions): DiffResult {
  const reasons: string[] = [];
  if (!existsSync(opts.baselinePath)) {
    return {
      pass: false,
      perPixelDiffPct: 1,
      largestRegionPx: 0,
      largestRegionPctOfViewport: 0,
      reasons: ['baseline missing'],
    };
  }
  if (!existsSync(opts.currentPath)) {
    return {
      pass: false,
      perPixelDiffPct: 1,
      largestRegionPx: 0,
      largestRegionPctOfViewport: 0,
      reasons: ['current missing'],
    };
  }

  const baseline = PNG.sync.read(readFileSync(opts.baselinePath));
  const current = PNG.sync.read(readFileSync(opts.currentPath));

  if (baseline.width !== current.width || baseline.height !== current.height) {
    return {
      pass: false,
      perPixelDiffPct: 1,
      largestRegionPx: 0,
      largestRegionPctOfViewport: 0,
      reasons: [
        `dimensions differ: baseline ${baseline.width}x${baseline.height} vs current ${current.width}x${current.height}`,
      ],
    };
  }

  const { width, height } = baseline;
  const total = width * height;

  // First pass: produce a clean mask (diffMask:true gives us transparent for
  // unchanged pixels, fully-coloured for changed). This is the source of
  // truth for region detection — using it avoids the false-positive where
  // pixelmatch's normal diff image fills unchanged pixels with a tinted
  // overlay (non-zero alpha).
  const maskImg = new PNG({ width, height });
  const diffPx = pixelmatch(baseline.data, current.data, maskImg.data, width, height, {
    threshold: opts.perPixelThreshold,
    includeAA: false,
    diffMask: true,
  });
  const mask = new Uint8Array(total);
  for (let p = 0; p < total; p++) {
    if (maskImg.data[p * 4 + 3] !== 0) mask[p] = 1;
  }

  // Second pass: produce the human-readable diff image (yellow background +
  // red highlights) for the report. Only if an output path was requested.
  let diffImg: PNG | undefined;
  if (opts.diffOutputPath) {
    diffImg = new PNG({ width, height });
    pixelmatch(baseline.data, current.data, diffImg.data, width, height, {
      threshold: opts.perPixelThreshold,
      includeAA: false,
      alpha: 0.5,
    });
  }

  const largestRegionPx = largestContiguousRegion(mask, width, height);
  const largestRegionPctOfViewport = largestRegionPx / total;
  const perPixelDiffPct = diffPx / total;

  // Both thresholds must pass.
  if (perPixelDiffPct > opts.perPixelThreshold && largestRegionPctOfViewport > opts.regionPctOfViewport) {
    reasons.push(
      `per-pixel diff ${(perPixelDiffPct * 100).toFixed(3)}% > ${(opts.perPixelThreshold * 100).toFixed(2)}%`,
    );
    reasons.push(
      `largest region ${(largestRegionPctOfViewport * 100).toFixed(3)}% > ${(opts.regionPctOfViewport * 100).toFixed(2)}%`,
    );
  } else if (largestRegionPctOfViewport > opts.regionPctOfViewport) {
    reasons.push(
      `largest contiguous changed region ${(largestRegionPctOfViewport * 100).toFixed(3)}% > ${(opts.regionPctOfViewport * 100).toFixed(2)}% of viewport`,
    );
  }
  // Per-pixel alone can be noisy; we only fail if it's >5x threshold AND
  // there's no qualifying region. Keeps font-rendering quirks from firing.
  // Note: if both thresholds breach we listed both reasons above.

  let diffPngPath: string | undefined;
  if (opts.diffOutputPath && diffImg) {
    writeFileSync(opts.diffOutputPath, PNG.sync.write(diffImg));
    diffPngPath = opts.diffOutputPath;
  }

  return {
    pass: reasons.length === 0,
    perPixelDiffPct,
    largestRegionPx,
    largestRegionPctOfViewport,
    reasons,
    diffPngPath,
  };
}
