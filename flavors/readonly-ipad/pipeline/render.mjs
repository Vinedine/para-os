// Node renderer driven by render.ps1.
// para-os-integration: readonly-ipad 2026.08.03 - see CHANGELOG.md; /para-upgrade reports drift against this line.
//
// Reads a JSON array of jobs from stdin:
//   [{ in: "<src path>", out: "<pdf path>", rel: "<display path>", type: "md" | "html" }, ...]
// Launches one headless Chromium for the whole batch. Markdown jobs are rendered
// to HTML with `marked` + github-markdown-css; html jobs (deal sheets) are
// self-contained styled documents loaded as-is. Both are printed to PDF.
//
// Output to stdout/stderr (one line per step) is consumed by render.ps1.
// Exits non-zero if any file failed.

// Use createRequire so we resolve via CJS (which honors NODE_PATH); ESM
// `import` does NOT honor NODE_PATH, so we cannot import globally installed
// packages by name with bare specifiers.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const t0 = Date.now();
const log = (msg) => process.stdout.write(`[render.mjs +${(((Date.now() - t0) / 1000)).toFixed(1)}s] ${msg}\n`);
const err = (msg) => process.stderr.write(`[render.mjs +${(((Date.now() - t0) / 1000)).toFixed(1)}s] ${msg}\n`);

log('boot: loading puppeteer, marked, github-markdown-css from global node_modules...');
const require = createRequire(import.meta.url);
const puppeteer = require('puppeteer');
const { marked } = require('marked');
const cssPath = require.resolve('github-markdown-css/github-markdown-light.css');
const markdownCss = readFileSync(cssPath, 'utf8');
log(`boot: stylesheet loaded (${markdownCss.length} bytes from ${cssPath})`);

log('boot: reading job list from stdin...');
const stdinChunks = [];
for await (const chunk of process.stdin) stdinChunks.push(chunk);
const jobs = JSON.parse(Buffer.concat(stdinChunks).toString('utf8'));
log(`boot: ${jobs.length} job(s) received`);

if (!Array.isArray(jobs) || jobs.length === 0) {
  err('no jobs on stdin');
  process.exit(0);
}

const wrap = (body) => `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
${markdownCss}
body {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
.markdown-body { font-size: 14px; }
.markdown-body table {
  display: table;
  width: 100%;
  table-layout: fixed;
}
.markdown-body th,
.markdown-body td {
  font-size: 12px;
  word-break: break-word;
  overflow-wrap: anywhere;
  vertical-align: top;
}
@page { size: A4; margin: 1.2cm; }
</style>
</head>
<body class="markdown-body">
${body}
</body>
</html>`;

log('boot: launching Chromium (first launch can take 30-60s while AV scans the binary)...');
const tBrowser = Date.now();
const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
log(`boot: Chromium up (${((Date.now() - tBrowser) / 1000).toFixed(1)}s)`);

const page = await browser.newPage();
log('boot: new page created, starting render loop\n');

// Render-vintage stamp: computed once, identical on every PDF in this batch, so a brief and
// its deal sheet rendered in the same run carry the same "Updated:" value. The reader of this
// flavor sees only PDFs and has no way to tell a fresh one from a stale one; same value on
// both means same vintage, which makes "are these two in sync?" an at-a-glance check.
const pad = (n) => String(n).padStart(2, '0');
const now = new Date();
const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
const footerTemplate = `<div style="width:100%;margin:0 0.6cm;font-size:8px;color:#8a8a8a;text-align:right;">Updated: ${stamp}</div>`;
const headerTemplate = '<div></div>'; // suppress Chromium's default header line
log(`boot: render stamp = ${stamp}`);

let rendered = 0;
let failed = 0;

for (let i = 0; i < jobs.length; i++) {
  const job = jobs[i];
  const tFile = Date.now();
  const prefix = `(${i + 1}/${jobs.length})`;
  try {
    if (job.type === 'html') {
      log(`${prefix} ${job.rel} - loading HTML document...`);
      const rawHtml = readFileSync(job.in, 'utf8');
      await page.setContent(rawHtml, { waitUntil: 'load' });

      log(`${prefix} ${job.rel} - printing PDF...`);
      await page.pdf({
        path: job.out,
        format: 'A4',
        printBackground: true,
        displayHeaderFooter: true,
        headerTemplate,
        footerTemplate,
        // bottom bumped 0.6->1cm to make room for the footer stamp; flow + the
        // @media print atomic-block rules absorb the minor reflow.
        margin: { top: '0.6cm', right: '0.6cm', bottom: '1cm', left: '0.6cm' },
      });
    } else {
      log(`${prefix} ${job.rel} - reading markdown...`);
      const md = readFileSync(job.in, 'utf8');

      log(`${prefix} ${job.rel} - parsing markdown (${md.length} bytes)...`);
      const html = wrap(marked.parse(md));

      log(`${prefix} ${job.rel} - loading into Chromium...`);
      await page.setContent(html, { waitUntil: 'load' });

      log(`${prefix} ${job.rel} - printing PDF...`);
      await page.pdf({
        path: job.out,
        format: 'A4',
        printBackground: true,
        displayHeaderFooter: true,
        headerTemplate,
        footerTemplate,
        margin: { top: '1.2cm', right: '1.2cm', bottom: '1.2cm', left: '1.2cm' },
      });
    }

    rendered++;
    log(`${prefix} ${job.rel} - ok (${((Date.now() - tFile) / 1000).toFixed(2)}s)\n`);
  } catch (e) {
    failed++;
    err(`${prefix} ${job.rel} - FAILED after ${((Date.now() - tFile) / 1000).toFixed(2)}s: ${e.message}\n`);
  }
}

log('shutdown: closing Chromium...');
await browser.close();

log(`done: ${rendered} rendered, ${failed} failed in ${((Date.now() - t0) / 1000).toFixed(1)}s total`);
process.exit(failed > 0 ? 1 : 0);
