// Cut a tall PNG into pieces short enough to read, top to bottom.
//
// USAGE:
//   node tools/dev/slice-png.js <in.png> [<slice-height>]
//
// Writes <in>-1.png, <in>-2.png, ... beside the input, each <slice-height>
// pixels tall (default 1600) apart from the last. The input must be under
// tmp/. Chromium does the cutting, so no image library is needed: the PNG is
// shown at 1:1 and each slice is a clipped screenshot of it.
//
// Needs WITH_PLAYWRIGHT=1 in kit.env (see tools/dev/shoot.js).
const path = require('path');
const { pathToFileURL } = require('url');

const [input, heightArg] = process.argv.slice(2);
const sliceHeight = Number(heightArg || 1600);
if (!input || !/^tmp\/[A-Za-z0-9._/-]+\.png$/.test(input) || input.includes('..')) {
  console.error('slice-png.js: give a .png under tmp/\nusage: node tools/dev/slice-png.js <in.png> [<slice-height>]');
  process.exit(2);
}
if (!Number.isInteger(sliceHeight) || sliceHeight < 100) {
  console.error(`slice-png.js: slice height must be a whole number of at least 100, not '${heightArg}'`);
  process.exit(2);
}

(async () => {
  // Required after the arguments are checked, so a usage error needs no browser.
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(path.resolve(input)).href);
  const { width, height } = await page.evaluate(() => {
    const img = document.querySelector('img');
    return { width: img.naturalWidth, height: img.naturalHeight };
  });
  // The image viewer centres and scales; a plain page at the image's own size does not.
  await page.setViewportSize({ width, height: Math.min(height, sliceHeight) });
  await page.setContent(`<body style="margin:0"><img src="${pathToFileURL(path.resolve(input)).href}" style="display:block"></body>`);
  await page.waitForLoadState('load');
  const stem = input.replace(/\.png$/, '');
  let n = 0;
  for (let y = 0; y < height; y += sliceHeight) {
    n += 1;
    const out = `${stem}-${n}.png`;
    await page.screenshot({ path: out, fullPage: true, clip: { x: 0, y, width, height: Math.min(sliceHeight, height - y) } });
    console.log(`${out} y=${y}`);
  }
  await browser.close();
})();
