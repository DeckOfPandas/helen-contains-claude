// Screenshot pages of a running site, full page, at phone and desktop widths.
//
// USAGE:
//   node tools/dev/shoot.js <base-url> <label> [--scheme light|dark] [--click <text>]... <path>...
//
//   node tools/dev/shoot.js http://127.0.0.1:9000/mysite before --scheme dark /now/ /year/
//   node tools/dev/shoot.js http://127.0.0.1:9000 menu --click "By colour" /
//
// Shots land in tmp/shots/<label>-<width>-<scheme>-<page>.png. Each --click
// clicks the first visible element with that exact text, in order, before the
// shot. Tall pages come out tall: tools/dev/slice-png.js cuts them into
// readable pieces.
//
// Needs WITH_PLAYWRIGHT=1 in kit.env. The image sets NODE_PATH to
// /opt/playwright/node_modules, so `require('playwright')` resolves with no
// prefix on the command.
const fs = require('fs');
const path = require('path');

const WIDTHS = { phone: 390, desktop: 1280 };
const OUT_DIR = 'tmp/shots';

function parse(argv) {
  const [base, label, ...rest] = argv;
  if (!base || !label) usage('give a base URL and a label');
  const opts = { base: base.replace(/\/$/, ''), label, scheme: 'light', clicks: [], paths: [] };
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === '--scheme') {
      opts.scheme = rest[++i];
      if (!['light', 'dark'].includes(opts.scheme)) usage(`--scheme is light or dark, not '${opts.scheme}'`);
    } else if (rest[i] === '--click') {
      if (rest[i + 1] === undefined) usage('--click needs the text to click');
      opts.clicks.push(rest[++i]);
    } else {
      opts.paths.push(rest[i]);
    }
  }
  if (!/^[A-Za-z0-9._-]+$/.test(label)) usage(`'${label}' must be letters, digits, . _ -`);
  if (opts.paths.length === 0) opts.paths.push('/');
  return opts;
}

function usage(message) {
  console.error(`shoot.js: ${message}\nusage: node tools/dev/shoot.js <base-url> <label> [--scheme light|dark] [--click <text>]... <path>...`);
  process.exit(2);
}

(async () => {
  const opts = parse(process.argv.slice(2));
  // Required after the arguments are checked, so a usage error needs no browser.
  const { chromium } = require('playwright');
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();
  let failed = false;
  for (const [name, width] of Object.entries(WIDTHS)) {
    const context = await browser.newContext({
      viewport: { width, height: 900 }, colorScheme: opts.scheme,
      isMobile: name === 'phone', hasTouch: name === 'phone', deviceScaleFactor: name === 'phone' ? 2 : 1,
    });
    const page = await context.newPage();
    for (const p of opts.paths) {
      const slug = p.replace(/^\/|\/$/g, '').replace(/[^A-Za-z0-9._-]+/g, '_') || 'root';
      const file = path.join(OUT_DIR, `${opts.label}-${name}-${opts.scheme}-${slug}.png`);
      try {
        await page.goto(opts.base + p, { waitUntil: 'networkidle' });
        for (const text of opts.clicks) {
          await page.getByText(text, { exact: true }).locator('visible=true').first().click();
          await page.waitForTimeout(200);
        }
        await page.waitForTimeout(300);
        await page.screenshot({ path: file, fullPage: true });
        console.log(`${name} ${p} -> ${file}`);
      } catch (e) {
        failed = true;
        console.log(`${name} ${p} ERROR ${e.message.split('\n')[0]}`);
      }
    }
    await context.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
