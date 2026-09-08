#!/usr/bin/env node
// Expects: Node.js 18+ on PATH. Reads ANTHROPIC_API_KEY (optional — direct API mode) and
// ANTHROPIC_BASE_URL (optional, defaults to https://api.anthropic.com). Without ANTHROPIC_API_KEY,
// falls back to the `claude` CLI on PATH (Claude Code, `claude -p --model haiku`).
// Example invocation: node classifier.mjs scraped.json niches.json classified.json --parallel 3
//   scraped.json is scraper.mjs's output; niches.json is a JSON array of allowed niche names,
//   e.g. ["SaaS","Finance","Marketing"]; classified.json is written as a JSON array of
//   {domain,primary,secondary,confidence}.
//
// Production Haiku batch classifier for domain niche classification.
// Auth strategy (in order):
//   1. ANTHROPIC_API_KEY → direct API call (cheapest: ~$0.05/1000 domains)
//   2. claude -p --model haiku with minimal system prompt (~$0.05-0.10/1000 domains)
// Features: parallel streams, crash recovery, adaptive batch sizing.
// Usage: node classifier.mjs <scraped.json> <niches.json> <output.json> [--parallel N]

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { spawn } from 'node:child_process';

// ── Config ──────────────────────────────────────────────────────────
const DEFAULT_BATCH_SIZE = 50;          // 50 domains per batch (small system prompt = room for more)
const API_BATCH_SIZE = 30;              // Slightly smaller for direct API (no json-schema enforcement)
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 3000;
const DEFAULT_PARALLEL = 3;

const SYSTEM_PROMPT = 'You are a website niche classifier. Given website data, classify each domain into a primary and secondary niche from the allowed list. Return ONLY a JSON object with a "classifications" array. Every domain must be classified — pick the closest match.';

const JSON_SCHEMA = JSON.stringify({
  type: 'object',
  properties: {
    classifications: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          domain: { type: 'string' },
          primary: { type: 'string' },
          secondary: { type: 'string' },
        },
        required: ['domain', 'primary', 'secondary'],
      },
    },
  },
  required: ['classifications'],
});

// ── Auth detection ──────────────────────────────────────────────────
const API_KEY = process.env.ANTHROPIC_API_KEY;
const BASE_URL = (process.env.ANTHROPIC_BASE_URL || 'https://api.anthropic.com').replace(/\/$/, '');
const USE_CLI = !API_KEY;

// ── Parse CLI args ──────────────────────────────────────────────────
const args = process.argv.slice(2);
const parallelIdx = args.indexOf('--parallel');
const PARALLEL = parallelIdx !== -1 ? parseInt(args[parallelIdx + 1], 10) || DEFAULT_PARALLEL : DEFAULT_PARALLEL;
const BATCH_SIZE = USE_CLI ? DEFAULT_BATCH_SIZE : API_BATCH_SIZE;

// ── Prompt builder ──────────────────────────────────────────────────
function buildPrompt(domains, niches) {
  const nicheList = niches.join(', ');
  const entries = domains.map(d => {
    const parts = [`Domain: ${d.domain}`];
    if (d.title) parts.push(`Title: ${d.title}`);
    if (d.meta) parts.push(`Meta: ${d.meta}`);
    if (d.headings) parts.push(`Headings: ${d.headings}`);
    if (d.body) parts.push(`Body: ${d.body.slice(0, 500)}`);
    if (d.aboutBody) parts.push(`About: ${d.aboutBody.slice(0, 300)}`);
    return parts.join('\n');
  }).join('\n---\n');

  return `Classify each website into a primary and secondary niche.

Allowed niches: ${nicheList}

Return a JSON object with "classifications" array containing exactly ${domains.length} entries.
Each entry: {"domain": "x.com", "primary": "Technology", "secondary": "SaaS"}

${entries}`;
}

// ── Direct API call (cheapest — when ANTHROPIC_API_KEY available) ───
async function callDirectAPI(prompt) {
  const resp = await fetch(`${BASE_URL}/v1/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5',
      max_tokens: 8192,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: prompt }],
    }),
  });

  if (resp.status === 429) {
    const retryAfter = parseInt(resp.headers.get('retry-after') || '10', 10);
    console.error(JSON.stringify({ event: 'rate_limited', retryAfterSec: retryAfter }));
    await new Promise(r => setTimeout(r, retryAfter * 1000));
    return callDirectAPI(prompt);
  }

  if (!resp.ok) throw new Error(`API ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  const data = await resp.json();
  return data.content[0].text;
}

// ── CLI call — minimal system prompt, no tool bloat ─────────────────
// Uses `env -u CLAUDECODE` to bypass nested session detection (same as deep-research skill).
// Does NOT use --output-format json — if timeout kills the process, JSON output is lost.
function callCLI(prompt) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    const errChunks = [];

    // Strip CLAUDECODE env var to allow nested claude -p inside containers
    const cleanEnv = { ...process.env, TERM: 'dumb' };
    delete cleanEnv.CLAUDECODE;

    const proc = spawn('claude', [
      '-p',
      '--model', 'haiku',
      '--system-prompt', SYSTEM_PROMPT,
      '--tools', '',
      '--no-session-persistence',
    ], {
      env: cleanEnv,
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 180_000,
    });

    proc.stdout.on('data', c => chunks.push(c));
    proc.stderr.on('data', c => errChunks.push(c));

    proc.on('close', code => {
      const stdout = Buffer.concat(chunks).toString();
      if (code !== 0) {
        const stderr = Buffer.concat(errChunks).toString();
        return reject(new Error(`claude exit ${code}: ${stderr.slice(0, 300)}`));
      }
      resolve(stdout);
    });

    proc.on('error', reject);
    proc.stdin.write(prompt);
    proc.stdin.end();
  });
}

// ── Parse response (handles both API and CLI formats) ───────────────
function parseResponse(text, niches, domains) {
  let classifications;

  try {
    const outer = JSON.parse(text);
    if (outer.result) {
      const inner = typeof outer.result === 'string' ? outer.result : JSON.stringify(outer.result);
      const match = inner.match(/\{[\s\S]*"classifications"[\s\S]*\}/);
      if (match) classifications = JSON.parse(match[0]).classifications;
      if (!classifications) {
        const arrMatch = inner.match(/\[[\s\S]*\]/);
        if (arrMatch) classifications = JSON.parse(arrMatch[0]);
      }
    }
    if (!classifications && outer.classifications) classifications = outer.classifications;
  } catch {}

  if (!classifications) {
    const match = text.match(/\{[\s\S]*"classifications"[\s\S]*\}/);
    if (match) classifications = JSON.parse(match[0]).classifications;
  }
  if (!classifications) {
    const arrMatch = text.match(/\[[\s\S]*\]/);
    if (arrMatch) classifications = JSON.parse(arrMatch[0]);
  }

  if (!classifications) throw new Error('Cannot parse classification response');

  return classifications.map((item, idx) => ({
    domain: item.domain || domains[idx]?.domain || '',
    primary: niches.includes(item.primary) ? item.primary : 'Unclassified',
    secondary: niches.includes(item.secondary) ? item.secondary : (item.primary || 'Unclassified'),
    confidence: domains[idx]?.status === 'ok' ? 'high' : 'low',
  }));
}

// ── Batch classify with retry ───────────────────────────────────────
async function classifyBatch(domains, niches, attempt = 0) {
  try {
    const prompt = buildPrompt(domains, niches);
    const text = USE_CLI ? await callCLI(prompt) : await callDirectAPI(prompt);
    return parseResponse(text, niches, domains);
  } catch (e) {
    if (attempt < MAX_RETRIES) {
      const backoff = RETRY_DELAY_MS * (attempt + 1);
      console.error(JSON.stringify({ event: 'retry', attempt: attempt + 1, error: e.message.slice(0, 200), backoffMs: backoff }));
      await new Promise(r => setTimeout(r, backoff));
      return classifyBatch(domains, niches, attempt + 1);
    }
    console.error(JSON.stringify({ event: 'batch_failed', error: e.message.slice(0, 200), domains: domains.map(d => d.domain) }));
    return domains.map(d => ({ domain: d.domain, primary: 'Unclassified', secondary: 'Unclassified', confidence: 'failed' }));
  }
}

// ── Parallel batch processor ────────────────────────────────────────
async function processStream(batches, niches, results, lock) {
  for (const batch of batches) {
    const classified = await classifyBatch(batch, niches);
    lock.push(...classified);
  }
}

// ── Main with crash recovery + parallel streams ─────────────────────
async function main() {
  const positionalArgs = args.filter((a, i) => a !== '--parallel' && args[i - 1] !== '--parallel');
  const [scrapedFile, nichesFile, outputFile] = positionalArgs;
  if (!scrapedFile || !nichesFile || !outputFile) {
    console.error('Usage: node classifier.mjs <scraped.json> <niches.json> <output.json> [--parallel N]');
    process.exit(1);
  }

  const scraped = JSON.parse(readFileSync(scrapedFile, 'utf8'));
  const niches = JSON.parse(readFileSync(nichesFile, 'utf8'));

  // Resume from existing output
  let results = [];
  const done = new Set();
  if (existsSync(outputFile)) {
    try {
      results = JSON.parse(readFileSync(outputFile, 'utf8'));
      for (const r of results) done.add(r.domain);
    } catch { results = []; }
  }

  const remaining = scraped.filter(d => !done.has(d.domain));

  // Split into batches
  const batches = [];
  for (let i = 0; i < remaining.length; i += BATCH_SIZE) {
    batches.push(remaining.slice(i, i + BATCH_SIZE));
  }

  console.error(JSON.stringify({
    phase: 'classify',
    auth: USE_CLI ? 'claude-cli' : 'api-key',
    systemPromptTokens: '~50',
    batchSize: BATCH_SIZE,
    parallel: PARALLEL,
    total: scraped.length,
    remaining: remaining.length,
    batches: batches.length,
    resumed: done.size,
  }));

  if (batches.length === 0) {
    console.error(JSON.stringify({ phase: 'classify', status: 'complete', total: scraped.length, classified: results.length }));
    return;
  }

  // Distribute batches across parallel streams (round-robin)
  const streams = Array.from({ length: Math.min(PARALLEL, batches.length) }, () => []);
  batches.forEach((batch, i) => streams[i % streams.length].push(batch));

  // Process all streams in parallel, collecting results into shared array
  const newResults = [];
  await Promise.all(streams.map(streamBatches => processStream(streamBatches, niches, newResults, newResults)));

  results.push(...newResults);

  // Save final results
  writeFileSync(outputFile, JSON.stringify(results));

  const unclassified = results.filter(r => r.primary === 'Unclassified').length;
  const highConf = results.filter(r => r.confidence === 'high').length;
  const lowConf = results.filter(r => r.confidence === 'low').length;

  console.error(JSON.stringify({
    phase: 'classify',
    status: 'complete',
    total: scraped.length,
    classified: results.length,
    unclassified,
    highConfidence: highConf,
    lowConfidence: lowConf,
  }));
}

main().catch(e => { console.error(e.message); process.exit(1); });
