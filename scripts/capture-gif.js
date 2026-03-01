#!/usr/bin/env node
/**
 * Captures the TARS flow slide animation as an animated GIF.
 * Uses Puppeteer (headless Chrome) for frames + gif-encoder-2 for GIF encoding.
 *
 * Install deps once:
 *   npm install puppeteer gif-encoder-2 pngjs
 *
 * Then run:
 *   node scripts/capture-gif.js
 */

const puppeteer  = require('puppeteer');
const GIFEncoder = require('gif-encoder-2');
const { PNG }    = require('pngjs');
const fs         = require('fs');
const path       = require('path');

// ── Config ────────────────────────────────────────────────────────────────────
const SLIDE_FILE  = path.resolve(__dirname, '..', 'tars-flow-slide-purple.html');
const OUTPUT_FILE = path.resolve(__dirname, '..', 'tars-flow.gif');

// Capture at 900×506 (75% of 1200×675 — keeps GIF file size reasonable)
const WIDTH  = 900;
const HEIGHT = 506;

const FPS           = 12;          // frames per second
const TOTAL_MS      = 4200;        // total capture duration (covers full animation)
const FRAME_DELAY   = Math.round(1000 / FPS); // ms between frames
const TOTAL_FRAMES  = Math.round(TOTAL_MS / FRAME_DELAY);
// ──────────────────────────────────────────────────────────────────────────────

async function main() {
  console.log('▶  TARS flow slide → animated GIF');
  console.log(`   Slide   : ${SLIDE_FILE}`);
  console.log(`   Output  : ${OUTPUT_FILE}`);
  console.log(`   Size    : ${WIDTH}×${HEIGHT}  |  ${FPS}fps  |  ${(TOTAL_MS/1000).toFixed(1)}s  |  ${TOTAL_FRAMES} frames`);
  console.log('');

  // ── 1. Launch headless Chrome ──────────────────────────────────────────────
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: 1 });

  await page.goto(`file://${SLIDE_FILE}`, { waitUntil: 'networkidle0' });

  // Let JS animations initialise (they start immediately on load)
  await sleep(200);

  // ── 2. Set up GIF encoder ──────────────────────────────────────────────────
  const encoder = new GIFEncoder(WIDTH, HEIGHT, 'neuquant', true);
  encoder.start();
  encoder.setRepeat(0);                // 0 = loop forever
  encoder.setDelay(FRAME_DELAY);
  encoder.setQuality(8);               // 1 (best) – 30 (worst). 8 is a good balance.
  encoder.setThreshold(10);            // only re-encode pixels that changed > 10%

  const gifChunks = [];
  const stream = encoder.createReadStream();
  stream.on('data', chunk => gifChunks.push(chunk));
  const streamDone = new Promise(resolve => stream.on('end', resolve));

  // ── 3. Capture frames ──────────────────────────────────────────────────────
  console.log('📸  Capturing frames...');
  const bar = progressBar(TOTAL_FRAMES);

  for (let i = 0; i < TOTAL_FRAMES; i++) {
    const pngBuf    = await page.screenshot({ encoding: 'binary' });
    const decoded   = PNG.sync.read(Buffer.from(pngBuf));
    encoder.addFrame(new Uint8ClampedArray(decoded.data));

    bar(i + 1);
    await sleep(FRAME_DELAY);
  }

  encoder.finish();
  await browser.close();

  // ── 4. Write GIF file ──────────────────────────────────────────────────────
  await streamDone;
  const gifBuf = Buffer.concat(gifChunks);
  fs.writeFileSync(OUTPUT_FILE, gifBuf);

  const sizeMB = (gifBuf.length / 1024 / 1024).toFixed(1);
  console.log('');
  console.log(`✅  Done! → ${OUTPUT_FILE}  (${sizeMB} MB)`);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function progressBar(total) {
  const width = 40;
  return function (current) {
    const pct  = current / total;
    const done = Math.round(pct * width);
    const bar  = '█'.repeat(done) + '░'.repeat(width - done);
    process.stdout.write(`\r   [${bar}] ${Math.round(pct * 100)}%  frame ${current}/${total}`);
    if (current === total) process.stdout.write('\n');
  };
}

main().catch(err => {
  console.error('\n❌  Error:', err.message);
  process.exit(1);
});
