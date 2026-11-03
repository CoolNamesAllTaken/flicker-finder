"""Slow-motion clips through the page's clip button (test/make_clip.py makes them):
  clip240.webm         240 fps as recorded: every frame must be decoded (requestVideoFrameCallback at a
                       reduced playbackRate) and analyzed at ~240 fps of real time
  clip240-slowed.webm  the same frames timed at 30 fps (a phone's slowed export); with the clip timing
                       chip set to 1/8 the analysis must again run at ~240 fps of real time
Checks: the sagging fixture is the hottest spot, steady fixtures stay at 0, the dips are caught as
events, almost no frame is skipped. Screenshots go to shots/."""
import http.server, threading, functools, json, sys, pathlib, time
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).resolve().parent.parent
SHELL = str(pathlib.Path.home() / '.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell')
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE)))
srv.RequestHandlerClass.log_message = lambda *a: None
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/index.html'
SHOTS = HERE / 'shots'; SHOTS.mkdir(exist_ok=True)
W, H = 390, 844
def to_screen(vx, vy):           # 360x640 video, object-fit: cover
    k = max(W / 360, H / 640); return (vx * k - (360 * k - W) / 2, vy * k - (640 * k - H) / 2)
FIX = [((36 if k == 0 else 216) + 54, int(640 * (0.07 + r * 0.235)) + 42) for r in range(4) for k in range(2)]   # fixture centers
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=SHELL, args=['--disable-gpu', '--autoplay-policy=no-user-gesture-required'])
    for name, tscale_taps in [x for x in (('clip240', 0), ('clip240-slowed', 2)) if len(sys.argv) < 2 or x[0] in sys.argv[1:]]:
        meta = json.load(open(HERE / f'test/{name}.json'))
        ctx = b.new_context(viewport={'width': W, 'height': H}, device_scale_factor=2); pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        pg.goto(url); pg.wait_for_timeout(800)
        pg.set_input_files('#file', str(HERE / f'test/{name}.webm'))
        pg.wait_for_function('FF.S.source === "clip"', timeout=15000)
        for _ in range(tscale_taps): pg.click('#exp')          # x1 -> 1/4 -> 1/8
        # one full pass of the clip (the dips start after the 0.8 s warm-up)
        t0 = time.time()
        pg.wait_for_function('FF.S.loops >= 1', timeout=1200000, polling=1000)
        info = pg.evaluate("""() => { const S = FF.S, an = S.an, v = document.getElementById('video');
          return {frameSrc: S.frameSrc, tscale: S.tscale, fps: +an.fps.toFixed(1), frames: an.frames, rate: +v.playbackRate.toFixed(3), clip: S.clip,
                  cols: an.cols, rows: an.rows, shown: Array.from(S.shown), parts: Array.from(S.shown, (_, c) => [+an.slow[c].toFixed(3), +an.fast[c].toFixed(4), +an.tr[c].toFixed(3)]), events: an.events.map(e => e.map(x => [+x[0].toFixed(3), +x[1].toFixed(3), x[2], +x[3].toFixed(3)])), t: an.lastT}; }""")
        info['wall_s'] = round(time.time() - t0, 1)
        cw, ch = W / info['cols'], H / info['rows']
        cell = lambda x, y: int(y // ch) * info['cols'] + int(x // cw)
        cells = [cell(*to_screen(*f)) for f in FIX]
        near = lambda c, t: abs(c % info['cols'] - t % info['cols']) <= 1 and abs(c // info['cols'] - t // info['cols']) <= 1
        dip = cells[3]; heat = info['shown']
        hot = sorted(range(len(heat)), key=lambda c: -heat[c])[:4]
        # steady fixtures: cells whose center lies on one of the other seven fixtures (108 x 84 video px)
        def owner(c):
            k = max(W / 360, H / 640); x = ((c % info['cols']) + 0.5) * cw; y = ((c // info['cols']) + 0.5) * ch
            vx, vy = (x + (360 * k - W) / 2) / k, (y + (640 * k - H) / 2) / k
            return next((i for i, (fx, fy) in enumerate(FIX) if abs(vx - fx) < 54 and abs(vy - fy) < 42), -1)
        steady = [c for c in range(len(heat)) if owner(c) not in (-1, 3)]
        elsewhere = [c for c in range(len(heat)) if owner(c) == -1 and not near(c, dip)]
        dur = meta['secs']; ev = info['events'][dip]
        # every dip should be met by an event of the sagging fixture's cell (within 20 ms)
        caught = sum(any(e[0] <= b_ + 0.02 and e[3] >= a - 0.02 for e in ev) for a, b_, _ in meta['dips'])
        expected = meta['fps'] * meta['secs']
        r = {k: info[k] for k in ('frameSrc', 'tscale', 'fps', 'frames', 'rate', 'clip', 'wall_s')}
        r.update(dip_cell=dip, hot=[[c, round(heat[c], 2)] for c in hot], worst_on_dip=near(hot[0], dip), dips=len(meta['dips']), caught_pass2=caught,
                 dip_events=len(ev), dip_event_list=[e for e in ev if e[0] < dur], steady_max=round(max(heat[c] for c in steady), 3), steady_cells=steady, elsewhere_max=[(c, round(heat[c], 3), info['parts'][c]) for c in elsewhere if heat[c] > 0.05], steady_events=sum(len(info['events'][c]) for c in steady), steady_event_cells={c: info['events'][c][:6] for c in steady if info['events'][c]},
                 frames_expected=expected, frames_analyzed=info['clip'].get('analyzed'), errors=errs)
        r['ok'] = (r['worst_on_dip'] and r['steady_max'] == 0 and r['steady_events'] == 0 and caught == len(meta['dips'])
                   and 220 <= r['fps'] <= 260 and (info['clip'].get('analyzed') or 0) >= 0.95 * expected and not errs)
        pg.mouse.click(*to_screen(*FIX[3])); pg.mouse.move(380, 300); pg.wait_for_timeout(1200)
        pg.screenshot(path=str(SHOTS / f'{name}-phone.png'))
        res[name] = r; ctx.close()
    b.close()
print(json.dumps(res))
ok = all(r['ok'] for r in res.values())
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
