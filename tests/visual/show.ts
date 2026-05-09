/**
 * Open baseline + current + diff side-by-side for a single state.
 *
 *   npm run snapshots:show -- <route> <state>
 *
 * Generates an HTML wrapper at __report__/<key>.html and opens it in the
 * default browser. Same wrapper format used by CI for diff artifacts.
 */
import { existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';
import { STATES, stateKey, type SnapshotState } from './states';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const BASE = resolve(__dirname, '__baselines__');
const PEND = resolve(__dirname, '__pending__');
const REPORT = resolve(__dirname, '__report__');
mkdirSync(REPORT, { recursive: true });

function buildHtml(key: string): string {
  return `<!doctype html>
<html><head>
<meta charset="utf-8">
<title>${key}</title>
<style>
  body { background:#0a0e14; color:#e6edf3; font:13px ui-monospace,Menlo,Consolas,monospace; padding:24px; }
  h1 { font-weight:500; font-size:14px; color:#00ffaa; margin:0 0 16px; }
  .grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }
  figure { background:#11161e; border:1px solid #1f2630; border-radius:6px; padding:8px; margin:0; }
  figcaption { font-size:11px; color:#8b96a8; margin-bottom:6px; text-transform:uppercase; letter-spacing:.08em; }
  img { width:100%; height:auto; display:block; image-rendering:pixelated; }
</style>
</head><body>
<h1>${key}</h1>
<div class="grid">
  <figure><figcaption>baseline</figcaption><img src="../__baselines__/${key}.png" alt="baseline"></figure>
  <figure><figcaption>current (pending)</figcaption><img src="../__pending__/${key}.png" alt="current"></figure>
  <figure><figcaption>diff</figcaption><img src="${key}.diff.png" alt="diff" onerror="this.parentElement.innerHTML+='<div style=color:#8b96a8;padding:8px;font-size:11px>no diff (no failure recorded)</div>'"></figure>
</div>
</body></html>`;
}

function openInBrowser(filePath: string) {
  const url = pathToFileURL(filePath).href;
  const platform = process.platform;
  const cmd =
    platform === 'win32' ? 'cmd' :
    platform === 'darwin' ? 'open' :
    'xdg-open';
  const args =
    platform === 'win32' ? ['/c', 'start', '', url] : [url];
  spawn(cmd, args, { stdio: 'ignore', detached: true }).unref();
}

function main() {
  const [route, state] = process.argv.slice(2);
  if (!route || !state) {
    console.error('Usage: snapshots:show <route> <state>');
    process.exit(2);
  }
  const decl = STATES.find((s: SnapshotState) => s.route === route && s.state === state);
  if (!decl) {
    console.error(`no declared state route=${route} state=${state}`);
    process.exit(1);
  }
  const key = stateKey(decl);
  if (!existsSync(resolve(BASE, `${key}.png`)) && !existsSync(resolve(PEND, `${key}.png`))) {
    console.error(`no baseline or pending capture for ${key}`);
    process.exit(1);
  }
  const html = buildHtml(key);
  const out = resolve(REPORT, `${key}.html`);
  writeFileSync(out, html);
  console.log(`opened ${out}`);
  openInBrowser(out);
}

main();
