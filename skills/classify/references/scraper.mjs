#!/usr/bin/env node
// Expects: Node.js 18+ on PATH (uses global fetch and node:dns/promises). No env vars read.
// No external services: plain HTTP fetch with a DNS pre-check, adaptive concurrency, and
// crash recovery (resumes from an existing output file).
// Example invocation: node scraper.mjs domains.json scraped.json
//   domains.json is a JSON array of bare domains: ["example.com","example.org"]
//   scraped.json is written as a JSON array of {domain,title,meta,headings,body,aboutBody,status}
//
// Production domain scraper for niche classification.
// Scrapes homepage + about page. Adaptive concurrency, DNS pre-check, crash recovery.
// Usage: node scraper.mjs <domains.json> <output.json>

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve4 } from 'node:dns/promises';

// ── Config ──────────────────────────────────────────────────────────
const INITIAL_CONCURRENCY = 30;
const MIN_CONCURRENCY = 5;
const BATCH_DELAY_MS = 500;
const DNS_TIMEOUT_MS = 3000;
const HTTP_TIMEOUT_MS = 8000;
const MAX_BODY_BYTES = 512_000;
const MAX_BODY_WORDS = 300;
const MAX_ABOUT_WORDS = 200;
const CHECKPOINT_EVERY = 100;
const ERROR_RATE_THRESHOLD = 0.5; // Halve concurrency if >50% errors in batch
const UA = 'Mozilla/5.0 (compatible; classify-skill/1.0; +https://scalably.io/skills/classify)';

// ── HTML extraction ─────────────────────────────────────────────────
function extractTitle(html) {
  const m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return m ? m[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().slice(0, 200) : '';
}

function extractMeta(html) {
  const m = html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([\s\S]*?)["']/i)
    || html.match(/<meta[^>]*content=["']([\s\S]*?)["'][^>]*name=["']description["']/i);
  return m ? m[1].replace(/\s+/g, ' ').trim().slice(0, 500) : '';
}

function extractHeadings(html) {
  const out = [];
  const re = /<h[12][^>]*>([\s\S]*?)<\/h[12]>/gi;
  let m;
  while ((m = re.exec(html)) && out.length < 10) {
    const t = m[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    if (t) out.push(t);
  }
  return out.join(' | ').slice(0, 500);
}

function extractBody(html, maxWords) {
  let clean = html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<nav[\s\S]*?<\/nav>/gi, '')
    .replace(/<header[\s\S]*?<\/header>/gi, '')
    .replace(/<footer[\s\S]*?<\/footer>/gi, '');
  const paras = [];
  const re = /<p[^>]*>([\s\S]*?)<\/p>/gi;
  let m;
  while ((m = re.exec(clean))) {
    const t = m[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    if (t.length > 20) paras.push(t);
  }
  return paras.join(' ').split(/\s+/).slice(0, maxWords).join(' ');
}

function findAboutLink(html, domain) {
  const re = /<a[^>]*href=["']([^"']*\/about[^"']*)["']/gi;
  let m;
  while ((m = re.exec(html))) {
    let href = m[1];
    if (href.startsWith('/')) return `https://${domain}${href}`;
    if (href.startsWith('http') && href.includes(domain)) return href;
  }
  return null;
}

// ── DNS pre-check ───────────────────────────────────────────────────
async function dnsResolves(domain) {
  try {
    await Promise.race([
      resolve4(domain),
      new Promise((_, rej) => setTimeout(() => rej(new Error('dns_timeout')), DNS_TIMEOUT_MS)),
    ]);
    return true;
  } catch {
    return false;
  }
}

// ── HTTP fetch with body cap ────────────────────────────────────────
async function fetchPage(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), HTTP_TIMEOUT_MS);
  try {
    const resp = await fetch(url, {
      signal: ctrl.signal,
      redirect: 'follow',
      headers: { 'User-Agent': UA },
    });
    if (!resp.ok) return null;
    const ct = resp.headers.get('content-type') || '';
    if (!ct.includes('html') && !ct.includes('xhtml')) return null;
    const reader = resp.body?.getReader();
    if (!reader) return null;
    const chunks = [];
    let size = 0;
    while (size < MAX_BODY_BYTES) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      size += value.length;
    }
    reader.cancel().catch(() => {});
    return new TextDecoder().decode(Buffer.concat(chunks));
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// ── Per-domain scrape ───────────────────────────────────────────────
async function scrapeDomain(domain) {
  // DNS pre-check: skip dead domains fast
  if (!await dnsResolves(domain)) {
    return { domain, title: '', meta: '', headings: '', body: '', aboutBody: '', status: 'error', errorType: 'dns' };
  }

  let html = await fetchPage(`https://${domain}`);
  if (!html) html = await fetchPage(`http://${domain}`);
  if (!html) {
    return { domain, title: '', meta: '', headings: '', body: '', aboutBody: '', status: 'error', errorType: 'http' };
  }

  const title = extractTitle(html);
  const meta = extractMeta(html);
  const headings = extractHeadings(html);
  const body = extractBody(html, MAX_BODY_WORDS);

  let aboutBody = '';
  const aboutUrl = findAboutLink(html, domain);
  if (aboutUrl) {
    const aboutHtml = await fetchPage(aboutUrl);
    if (aboutHtml) aboutBody = extractBody(aboutHtml, MAX_ABOUT_WORDS);
  }

  return { domain, title, meta, headings, body, aboutBody, status: 'ok' };
}

// ── Main with adaptive concurrency ──────────────────────────────────
async function main() {
  const [,, inputFile, outputFile] = process.argv;
  if (!inputFile || !outputFile) {
    console.error('Usage: node scraper.mjs <domains.json> <output.json>');
    process.exit(1);
  }

  const allDomains = JSON.parse(readFileSync(inputFile, 'utf8'));

  // Resume from existing output
  let results = [];
  const done = new Set();
  if (existsSync(outputFile)) {
    try {
      results = JSON.parse(readFileSync(outputFile, 'utf8'));
      for (const r of results) done.add(r.domain);
      console.error(JSON.stringify({ phase: 'scrape', resuming: true, alreadyDone: done.size }));
    } catch { results = []; }
  }

  const domains = allDomains.filter(d => !done.has(d));
  let ok = results.filter(r => r.status === 'ok').length;
  let err = results.filter(r => r.status !== 'ok').length;
  let concurrency = INITIAL_CONCURRENCY;
  let delay = BATCH_DELAY_MS;

  for (let i = 0; i < domains.length; i += concurrency) {
    const batch = domains.slice(i, i + concurrency);
    const settled = await Promise.allSettled(batch.map(scrapeDomain));

    let batchOk = 0, batchErr = 0;
    for (const r of settled) {
      const val = r.status === 'fulfilled' ? r.value : { domain: '', status: 'error', errorType: 'exception' };
      results.push(val);
      if (val.status === 'ok') { ok++; batchOk++; }
      else { err++; batchErr++; }
    }

    // Adaptive concurrency: if >50% errors, slow down
    const batchErrorRate = batchErr / (batchOk + batchErr);
    if (batchErrorRate > ERROR_RATE_THRESHOLD && concurrency > MIN_CONCURRENCY) {
      concurrency = Math.max(MIN_CONCURRENCY, Math.floor(concurrency * 0.6));
      delay = Math.min(delay + 500, 3000);
      console.error(JSON.stringify({ phase: 'scrape', adaptive: true, newConcurrency: concurrency, newDelay: delay }));
    } else if (batchErrorRate < 0.2 && concurrency < INITIAL_CONCURRENCY) {
      // Recover if error rate drops
      concurrency = Math.min(concurrency + 5, INITIAL_CONCURRENCY);
      delay = Math.max(delay - 200, BATCH_DELAY_MS);
    }

    const progress = done.size + Math.min(i + concurrency, domains.length);
    console.error(JSON.stringify({ phase: 'scrape', progress, total: allDomains.length, ok, errors: err, concurrency }));

    // Checkpoint
    if (results.length % CHECKPOINT_EVERY < concurrency) {
      writeFileSync(outputFile, JSON.stringify(results));
    }

    // Delay between batches
    await new Promise(r => setTimeout(r, delay));
  }

  writeFileSync(outputFile, JSON.stringify(results));
  console.error(JSON.stringify({ phase: 'scrape', status: 'complete', total: allDomains.length, ok, errors: err }));
}

main().catch(e => { console.error(e.message); process.exit(1); });
