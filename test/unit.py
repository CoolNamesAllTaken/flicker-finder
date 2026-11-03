"""Synthetic frames through the page's Analyzer: one cell at 4 Hz, one with banding, AE drift on all."""
import json, sys, pathlib
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).resolve().parent.parent
SHELL = str(pathlib.Path.home() / '.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell')
JS = r"""
() => {
  const aw = 120, ah = 200, cols = 6, rows = 10, an = new FF.Analyzer(cols, rows, aw, ah);
  const cv = document.createElement('canvas'); cv.width = aw; cv.height = ah; const ctx = cv.getContext('2d', {willReadFrequently: true});
  // fixtures: lit rectangles at cells (1,2) slow, (4,6) banded, (1,6) and (4,2) steady
  const fx = [[1,2],[4,6],[1,6],[4,2]];
  const cw = aw/cols, ch = ah/rows;
  for (let i = 0; i < 120; i++) {               // 4 s at 30 fps
    const t = i / 30, gain = 1 + 0.25 * Math.sin(2*Math.PI*0.7*t);      // camera AE wandering
    ctx.fillStyle = `rgb(${50*gain},${50*gain},${50*gain})`; ctx.fillRect(0,0,aw,ah);
    fx.forEach(([cx,cy], k) => {
      let lvl = 200 * gain;
      if (k === 0) lvl *= 0.75 + 0.25*Math.sin(2*Math.PI*4*t);
      ctx.fillStyle = `rgb(${lvl},${lvl},${lvl})`; ctx.fillRect(cx*cw+2, cy*ch+2, cw-4, ch-4);
      if (k === 1) for (let y = 0; y < ch-4; y++) {
        const a = 0.5+0.5*Math.sin(2*Math.PI*(y/6 - t*0.5));
        ctx.fillStyle = `rgba(0,0,0,${0.3*a})`; ctx.fillRect(cx*cw+2, cy*ch+2+y, cw-4, 1);
      }
    });
    an.frame(ctx.getImageData(0,0,aw,ah).data, t);
  }
  const idx = (cx,cy) => cy*cols+cx, heat = an.heat('both', 1);
  const rank = a => Array.from(a).map((v,i)=>[v,i]).sort((x,y)=>y[0]-x[0]).slice(0,3).map(([v,i])=>[i, +v.toFixed(4)]);
  return {slowTop: rank(an.slow), fastTop: rank(an.fast), heatTop: rank(heat),
          slowCell: idx(1,2), fastCell: idx(4,6), freq: an.freq[idx(1,2)],
          steady: [idx(1,6), idx(4,2)].map(c => [+an.slow[c].toFixed(4), +an.fast[c].toFixed(4), +heat[c].toFixed(3)])};
}
"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=SHELL)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto((HERE / 'index.html').as_uri()); pg.wait_for_timeout(500)
    r = pg.evaluate(JS); b.close()
print(json.dumps(r, indent=1)); print('errors', errs)
ok = (r['slowTop'][0][0] == r['slowCell'] and r['fastTop'][0][0] == r['fastCell'] and abs(r['freq'] - 4) <= 0.5
      and {r['heatTop'][0][0], r['heatTop'][1][0]} == {r['slowCell'], r['fastCell']} and all(h < 0.1 for *_, h in r['steady']) and not errs)
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
