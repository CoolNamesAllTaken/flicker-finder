"""Synthetic frames through the page's Analyzer in headless Chromium.
  original  one cell at 4 Hz, one with banding, AE drift on all (the first version's test)
  dips      a lamp with random dips (10-40 %, 20-100 ms, every 0.1-2 s), rolling shutter, jittered frame times, 30 and 60 fps
  pwm       1 kHz and 2.5 kHz PWM stripes (30 % deep; and 2.5 kHz at 12 %) on a 1080x1920 portrait video, through the app's own grab path
            (full-resolution line strips), versus the same frames with the line strips turned off
Each case: the right cell scores highest and steady fixtures stay at 0."""
import json, sys, pathlib
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).resolve().parent.parent
SHELL = str(pathlib.Path.home() / '.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell')

ORIGINAL = r"""
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

# Rolling shutter: row y is exposed at t + y/ah * readout, for `exp` seconds; the lamp's level is
# averaged over that exposure. Frame times jitter by +-3 ms like a real camera.
DIPS = r"""
({fps, secs, seed}) => {
  const aw = 120, ah = 200, cols = 6, rows = 10, an = new FF.Analyzer(cols, rows, aw, ah);
  const cv = document.createElement('canvas'); cv.width = aw; cv.height = ah; const ctx = cv.getContext('2d', {willReadFrequently: true});
  let s = seed; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const dips = []; for (let t = 0.4 + rnd(); t < secs - 0.1; ) { const len = 0.02 + 0.08 * rnd(); dips.push([t, t + len, 0.1 + 0.3 * rnd()]); t += len + 0.1 + 1.9 * rnd(); }
  const lamp = tt => { for (const [a, b, d] of dips) if (tt >= a && tt < b) return 1 - d; return 1; };
  const READ = 0.8 / fps, EXP = 0.004, cw = aw / cols, ch = ah / rows;
  const fx = [[1, 2], [4, 6], [1, 6], [4, 2]];          // dipping, then three steady
  let last = -1, frames = 0;
  for (let i = 0; i < fps * secs; i++) {
    const t = Math.max(last + 0.002, i / fps + (rnd() - 0.5) * 0.006); last = t;
    const gain = 1 + 0.2 * Math.sin(2 * Math.PI * 0.5 * t);
    ctx.fillStyle = `rgb(${50 * gain},${50 * gain},${50 * gain})`; ctx.fillRect(0, 0, aw, ah);
    fx.forEach(([cx, cy], k) => {
      for (let y = cy * ch + 2; y < (cy + 1) * ch - 2; y++) {
        let lvl = 1;
        if (k === 0) { const tt = t + y / ah * READ; lvl = 0; for (let q = 0; q < 4; q++) lvl += lamp(tt + EXP * (q + 0.5) / 4) / 4; }
        const v = 200 * gain * lvl; ctx.fillStyle = `rgb(${v},${v},${v})`; ctx.fillRect(cx * cw + 2, y, cw - 4, 1);
      }
    });
    const img = ctx.getImageData(0, 0, aw, ah), d = img.data;
    for (let p = 0; p < d.length; p += 4) { const nz = (rnd() - 0.5) * 6; d[p] += nz; d[p + 1] += nz; d[p + 2] += nz; }
    an.frame(d, t); frames++;
  }
  const idx = (cx, cy) => cy * cols + cx, dip = idx(1, 2), steady = [idx(4, 6), idx(1, 6), idx(4, 2)];
  const rank = a => Array.from(a).map((v, i) => [v, i]).sort((x, y) => y[0] - x[0]).slice(0, 3).map(([v, i]) => [i, +v.toFixed(4)]);
  // A dip counts as caught if an event of the dipping cell overlaps it (within a frame).
  const ev = an.events[dip], caught = dips.filter(([a, b]) => ev.some(e => e[0] <= b + 1.5 / fps && e[3] >= a - 1.5 / fps)).length;
  const both = an.heat('both', 1), tr = an.heat('transient', 1), slow = an.heat('slow', 1), fast = an.heat('fast', 1);
  return {fps, frames, dips: dips.length, caught, dipEvents: ev.length, heatTop: rank(both), trTop: rank(an.tr), dipCell: dip,
          dipHeat: {both: +both[dip].toFixed(3), transient: +tr[dip].toFixed(3), slowOnly: +slow[dip].toFixed(3), fastOnly: +fast[dip].toFixed(3)},
          measuredFps: +an.fps.toFixed(1),
          steady: steady.map(c => ({cell: c, heat: +both[c].toFixed(3), events: an.events[c].length}))};
}
"""

# A 1080x1920 portrait frame (sensor rows run along x) with a 2 x 4 grid of fixtures; fixture 2
# (row 1, left) is PWM-dimmed at `hz`: each column is exposed at t + x/1080 * readout for 1/4000 s,
# brightness 1 - depth + depth x the share of that exposure the LED is on. Fed through FF.grabFrom, the
# app's own crop + downsample + full-resolution line strips.
PWM = r"""
({hz, fps, secs, lines, depth = 0.3}) => {
  const S = FF.S; S.running = false; S.lines = lines; S.linesT = undefined; FF.layout();
  const W = 1080, H = 1920, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const ctx = cv.getContext('2d'), img = ctx.createImageData(W, H), d = img.data;
  let s = 11; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const noise = new Float32Array(1 << 16); for (let i = 0; i < noise.length; i++) noise[i] = (rnd() - 0.5) * 6;
  const fx = []; for (let r = 0; r < 4; r++) for (let k = 0; k < 2; k++) fx.push([k ? 648 : 108, Math.round(H * (0.07 + r * 0.235)), 324, 252]);
  const PW = 2, READ = 1 / fps, EXP = 1 / 4000, duty = 0.5, per = 1 / hz;
  const on = (a, b) => { let tot = 0; for (let q = 0; q < 8; q++) { const u = a + (b - a) * (q + 0.5) / 8; tot += ((u / per) % 1) < duty ? 1 : 0; } return tot / 8; };
  const col = new Float32Array(W);
  for (let i = 0; i < fps * secs; i++) {
    const t = i / fps, gain = 1 + 0.1 * Math.sin(2 * Math.PI * 0.4 * t);
    for (let x = 0; x < W; x++) { const tt = t + x / W * READ; col[x] = 1 - depth + depth * on(tt, tt + EXP); }
    let z = (i * 7919) & 0xffff;
    for (let y = 0; y < H; y++) {
      let f = -1; for (let j = 0; j < fx.length; j++) { const [x0, y0, w, h] = fx[j]; if (y >= y0 && y < y0 + h) { f = j; break; } }
      for (let x = 0, p = y * W * 4; x < W; x++, p += 4) {
        let v = 60;
        if (f >= 0) { const [x0, , w] = fx[f]; if (x >= x0 && x < x0 + w) v = 220 * (f === PW ? col[x] : 1); }
        v = v * gain + noise[z = (z + 1) & 0xffff]; d[p] = d[p + 1] = d[p + 2] = v; d[p + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    FF.grabFrom(cv, W, H, t);
  }
  // Which grid cells sit on which fixture (cell center inside it), through the same crop as the app.
  const an = S.an, sw = innerWidth, sh = innerHeight, k = Math.max(sw / W, sh / H), vw = sw / k, vh = sh / k, ox = (W - vw) / 2, oy = (H - vh) / 2;
  const on_ = c => { const x = ox + ((c % an.cols) + 0.5) * vw / an.cols, y = oy + (((c / an.cols) | 0) + 0.5) * vh / an.rows;
    return fx.findIndex(([x0, y0, w, h]) => x >= x0 && x < x0 + w && y >= y0 && y < y0 + h); };
  const n = an.cols * an.rows, heat = an.heat('both', 1), owner = Array.from({length: n}, (_, c) => on_(c));
  const pwmCells = owner.map((f, c) => f === PW ? c : -1).filter(c => c >= 0);
  const steadyCells = owner.map((f, c) => f >= 0 && f !== PW ? c : -1).filter(c => c >= 0);
  const top = Array.from(an.fast).map((v, i) => [v, i]).sort((a, b) => b[0] - a[0])[0][1];
  const best = pwmCells.reduce((a, c) => heat[c] > heat[a] ? c : a, pwmCells[0]);
  S.lines = true; S.running = true;
  return {hz, lines, topFastCell: top, topOnPwm: pwmCells.includes(top), pwmCells, pwmHeat: +heat[best].toFixed(3), pwmFast: +an.fast[best].toFixed(4),
          stripeHz: Math.round(an.sfreq[best]), steadyMax: +Math.max(...steadyCells.map(c => heat[c])).toFixed(3), frames: an.frames};
}
"""

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=SHELL)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto((HERE / 'index.html').as_uri()); pg.wait_for_timeout(500)
    R = {'original': pg.evaluate(ORIGINAL)}
    R['dips30'] = pg.evaluate(DIPS, {'fps': 30, 'secs': 10, 'seed': 3})
    R['dips60'] = pg.evaluate(DIPS, {'fps': 60, 'secs': 10, 'seed': 5})
    for name, hz, depth in (('pwm1000', 1000, 0.3), ('pwm2500', 2500, 0.3), ('pwm2500weak', 2500, 0.12)):
        for lines in (True, False):
            R[name + ('' if lines else '_nolines')] = pg.evaluate(PWM, {'hz': hz, 'fps': 30, 'secs': 3, 'lines': lines, 'depth': depth})
    b.close()
print(json.dumps(R, indent=1)); print('errors', errs)

r = R['original']
ok = {'original': r['slowTop'][0][0] == r['slowCell'] and r['fastTop'][0][0] == r['fastCell'] and abs(r['freq'] - 4) <= 0.5
      and {r['heatTop'][0][0], r['heatTop'][1][0]} == {r['slowCell'], r['fastCell']} and all(h < 0.1 for *_, h in r['steady'])}
for k in ('dips30', 'dips60'):
    r = R[k]
    ok[k] = (r['heatTop'][0][0] == r['dipCell'] and r['trTop'][0][0] == r['dipCell'] and r['dipHeat']['both'] > 0.5
             and r['caught'] >= 0.7 * r['dips'] and all(s['heat'] == 0 and s['events'] == 0 for s in r['steady']))
for k in ('pwm1000', 'pwm2500', 'pwm2500weak'):
    r = R[k]; hz = r['hz']
    ok[k] = r['topOnPwm'] and r['pwmHeat'] > 0.5 and abs(r['stripeHz'] / hz - 1) < 0.15 and r['steadyMax'] == 0
for k, v in ok.items(): print(f'{k:10s} {"PASS" if v else "FAIL"}')
ok = all(ok.values()) and not errs
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
