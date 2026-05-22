/**
 * Generate the HTML failure report from the latest capture run.
 *
 *   __report__/visual.html        ← summary + thumbnail grid
 *   __report__/summary.<N>.json   ← per-worker raw records (one per Playwright worker)
 *
 * Reads ALL `summary.*.json` files in __report__/ (written by capture.spec.ts
 * afterAll, one per worker). Merges and deduplicates by state key — latest
 * file mtime wins on dedup, so a re-run with fewer workers does not see stale
 * records leak through. Pre-fix bug: a single shared summary.json was
 * overwritten by the last worker's afterAll, surfacing only ~4 of 14 records.
 *
 * § 11 layout: short summary first, diff thumbnails second, raw last.
 */
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPORT_DIR = resolve(__dirname, '__report__');
mkdirSync(REPORT_DIR, { recursive: true });

interface Row {
  key: string;
  status: 'baseline-missing' | 'pass' | 'fail' | 'capture-error';
  perPixelDiffPct?: number;
  largestRegionPctOfViewport?: number;
  reasons: string[];
  explicitReady?: boolean;
}

function loadSummary(): Row[] {
  // Collect all per-worker summaries + any legacy single-file summary.json
  // that may persist from pre-fix runs. Each file holds an array of Row.
  let files: { path: string; mtimeMs: number }[];
  try {
    files = readdirSync(REPORT_DIR)
      .filter(f => /^summary\.\d+\.json$/.test(f) || f === 'summary.json')
      .map(f => {
        const p = resolve(REPORT_DIR, f);
        return { path: p, mtimeMs: statSync(p).mtimeMs };
      });
  } catch {
    return [];
  }
  if (files.length === 0) return [];

  // Sort ASCENDING by mtime so newer files iterate LAST. With a single Map
  // keyed by `key`, later iterations overwrite earlier ones — latest mtime
  // wins on dedup, which is the correct semantics when worker count or
  // state list changes between runs.
  files.sort((a, b) => a.mtimeMs - b.mtimeMs);

  const seen = new Map<string, Row>();
  for (const { path } of files) {
    try {
      const data = JSON.parse(readFileSync(path, 'utf8')) as Row[];
      if (!Array.isArray(data)) continue;
      for (const r of data) {
        if (r && typeof r.key === 'string') seen.set(r.key, r);
      }
    } catch {
      // Malformed per-worker file: skip without failing the whole report.
      // Aggregation is best-effort; a single bad file does not block the rest.
    }
  }
  return Array.from(seen.values()).sort((a, b) => a.key.localeCompare(b.key));
}

function statusBadge(s: Row['status']): string {
  if (s === 'pass') return `<span style="color:#00ffaa">PASS</span>`;
  if (s === 'baseline-missing') return `<span style="color:#ffcc66">PEND</span>`;
  if (s === 'capture-error') return `<span style="color:#ff5577">ERR</span>`;
  return `<span style="color:#ff5577">FAIL</span>`;
}

function buildHtml(rows: Row[]): string {
  const counts = {
    pass: rows.filter(r => r.status === 'pass').length,
    fail: rows.filter(r => r.status === 'fail').length,
    pend: rows.filter(r => r.status === 'baseline-missing').length,
    err: rows.filter(r => r.status === 'capture-error').length,
  };
  const summaryLine = `pass:${counts.pass}  fail:${counts.fail}  baseline-missing:${counts.pend}  error:${counts.err}  total:${rows.length}`;
  const failures = rows.filter(r => r.status === 'fail' || r.status === 'capture-error');

  const failureGrid = failures.length === 0
    ? `<p style="color:#8b96a8">no failures.</p>`
    : failures
        .map(r => `
        <div class="grid">
          <h2>${r.key} ${statusBadge(r.status)}</h2>
          <p class="reasons">${r.reasons.map(x => `<span class="reason">${x}</span>`).join(' ')}</p>
          <div class="trip">
            <figure><figcaption>baseline</figcaption><img src="../__baselines__/${r.key}.png" onerror="this.style.display='none'"></figure>
            <figure><figcaption>current</figcaption><img src="../__pending__/${r.key}.png" onerror="this.style.display='none'"></figure>
            <figure><figcaption>diff</figcaption><img src="./${r.key}.diff.png" onerror="this.style.display='none'"></figure>
          </div>
        </div>
        `)
        .join('');

  return `<!doctype html>
<html><head>
<meta charset="utf-8">
<title>visual snapshot report</title>
<style>
  body { background:#0a0e14; color:#e6edf3; font:13px ui-monospace,Menlo,Consolas,monospace; padding:24px; max-width:1400px; margin:0 auto; }
  h1 { font-weight:500; font-size:16px; color:#00ffaa; margin:0 0 8px; }
  .summary { padding:12px 14px; background:#11161e; border:1px solid #1f2630; border-radius:6px; margin-bottom:24px; }
  h2 { font-size:13px; font-weight:500; margin:0 0 6px; }
  .grid { margin-bottom:32px; padding:14px; background:#0d1218; border:1px solid #1f2630; border-radius:6px; }
  .reasons { color:#8b96a8; margin:0 0 10px; }
  .reason { display:inline-block; padding:2px 6px; background:#1a212c; border-radius:3px; margin-right:6px; font-size:11px; }
  .trip { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }
  figure { margin:0; background:#11161e; border:1px solid #1f2630; border-radius:4px; padding:6px; }
  figcaption { font-size:10px; color:#8b96a8; margin-bottom:4px; text-transform:uppercase; letter-spacing:.08em; }
  img { width:100%; height:auto; display:block; image-rendering:pixelated; }
  table { width:100%; border-collapse:collapse; margin-top:24px; font-size:12px; }
  th, td { padding:6px 8px; border-bottom:1px solid #1f2630; text-align:left; }
  th { color:#8b96a8; font-weight:500; }
  .raw { color:#8b96a8; font-size:11px; margin-top:24px; }
</style>
</head><body>
<h1>visual snapshot report</h1>
<div class="summary">${summaryLine}</div>

<h2 style="color:#ffcc66">FAILURES</h2>
${failureGrid}

<h2 style="color:#8b96a8">ALL STATES</h2>
<table>
  <tr><th>state</th><th>status</th><th>per-pixel %</th><th>largest region %</th><th>ready flag</th></tr>
  ${rows.map(r => `<tr>
    <td>${r.key}</td>
    <td>${statusBadge(r.status)}</td>
    <td>${r.perPixelDiffPct != null ? (r.perPixelDiffPct * 100).toFixed(3) : '—'}</td>
    <td>${r.largestRegionPctOfViewport != null ? (r.largestRegionPctOfViewport * 100).toFixed(3) : '—'}</td>
    <td>${r.explicitReady ? '✓' : '·'}</td>
  </tr>`).join('')}
</table>

<p class="raw">raw machine-readable: <code>__report__/summary.&lt;workerIndex&gt;.json</code> (one per Playwright worker; merged in-memory)</p>
</body></html>`;
}

function main() {
  const rows = loadSummary();
  if (rows.length === 0) {
    console.error('No summary.<workerIndex>.json files found in __report__/. Run `npm run snapshots:capture` first.');
    process.exit(1);
  }
  const html = buildHtml(rows);
  const out = resolve(REPORT_DIR, 'visual.html');
  writeFileSync(out, html);

  // Short summary to stdout — same § 11 ordering.
  const counts = {
    pass: rows.filter(r => r.status === 'pass').length,
    fail: rows.filter(r => r.status === 'fail').length,
    pend: rows.filter(r => r.status === 'baseline-missing').length,
    err: rows.filter(r => r.status === 'capture-error').length,
  };
  console.log(`pass:${counts.pass}  fail:${counts.fail}  baseline-missing:${counts.pend}  error:${counts.err}  total:${rows.length}`);
  for (const r of rows.filter(r => r.status !== 'pass')) {
    console.log(`  ${r.status.padEnd(18)} ${r.key} — ${r.reasons.join('; ')}`);
  }
  console.log(`\nreport: ${out}`);
}

main();
