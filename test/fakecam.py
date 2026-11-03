"""Fake camera (test/ceiling.y4m) into the page at phone size; screenshot the heatmap and check the worst
cell sits on the dropping-out fixture (row 2, right) and the striped one (row 0, left) glows too."""
import http.server, threading, functools, json, sys, pathlib
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).resolve().parent.parent
SHELL = str(pathlib.Path.home() / '.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell')
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE), ))
srv.RequestHandlerClass.log_message = lambda *a: None
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{srv.server_address[1]}/index.html'
SHOTS = HERE / 'shots'; SHOTS.mkdir(exist_ok=True)
# fixture centers in video px (360x640): slow = (270, 387), banded = (90, 87)
def to_screen(vx, vy, W, H):
    k = max(W / 360, H / 640); return (vx * k - (360 * k - W) / 2, vy * k - (640 * k - H) / 2)
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=SHELL, args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
        f'--use-file-for-fake-video-capture={HERE / "test/ceiling.y4m"}', '--use-angle=swiftshader'])
    for name, W, H in (('phone', 390, 844), ('desktop', 1280, 800)):
        ctx = b.new_context(viewport={'width': W, 'height': H}, permissions=['camera'], device_scale_factor=2 if name == 'phone' else 1)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        pg.goto(url + '?camera'); pg.wait_for_timeout(6000)
        info = pg.evaluate("""() => { const S = FF.S, an = S.an; const hot = Array.from(S.shown).map((v,i)=>[v,i]).sort((a,b)=>b[0]-a[0]).slice(0,4);
            return {source: S.source, cols: an.cols, rows: an.rows, W: innerWidth, H: innerHeight, hot: hot.map(([v,i]) => [i, +v.toFixed(2)])}; }""")
        cw, ch = info['W'] / info['cols'], info['H'] / info['rows']
        cell = lambda x, y: int(y // ch) * info['cols'] + int(x // cw)
        slow = cell(*to_screen(270, 387, W, H)); band = cell(*to_screen(90, 87, W, H))
        near = lambda c, t: abs(c % info['cols'] - t % info['cols']) <= 1 and abs(c // info['cols'] - t // info['cols']) <= 1
        info.update(slow_cell=slow, band_cell=band, errors=errs,
                    worst_on_slow=near(info['hot'][0][0], slow),
                    band_heat=None if band < 0 else pg.evaluate(f'Math.max(...[-1,0,1].flatMap(dy => [-1,0,1].map(dx => {band} + dy*{info["cols"]} + dx)).map(c => FF.S.shown[c] || 0))'))
        # the six fixtures that are steady: no cell may glow; measured over cells away from both bad fixtures
        heat = pg.evaluate('Array.from(FF.S.shown)')
        bad = {c for t in (slow, band) if t >= 0 for c in range(len(heat)) if near(c, t)}
        info['steady_max'] = round(max(v for c, v in enumerate(heat) if c not in bad), 3)
        info['grid'] = [[round(heat[r*info['cols']+k],2) for k in range(info['cols'])] for r in range(info['rows'])] if name == 'desktop' else None
        info['parts'] = pg.evaluate('(() => { const a = FF.S.an; return [Array.from(a.slow).map(v=>+v.toFixed(3)), Array.from(a.fast).map(v=>+v.toFixed(3))]; })()') if name == 'desktop' else None
        info['band_glows'] = info['band_heat'] is None or info['band_heat'] > 0.25
        pg.screenshot(path=str(SHOTS / f'fakecam-{name}.png'))
        if name == 'phone':   # pin the worst spot, then a second shot
            sx, sy = to_screen(270, 387, W, H); pg.mouse.click(sx, sy); pg.wait_for_timeout(1500)
            pg.screenshot(path=str(SHOTS / 'fakecam-phone-pinned.png'))
            pg.click('#info'); pg.wait_for_timeout(300); pg.screenshot(path=str(SHOTS / 'legend-phone.png'))
        res[name] = info; ctx.close()
    b.close()
    # Demo mode (what the published artifact opens with) and a denied camera: a browser that
    # neither fakes nor auto-accepts the camera.
    b = p.chromium.launch(executable_path=SHELL, args=['--use-angle=swiftshader', '--deny-permission-prompts'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2); pg = ctx.new_page()
    pg.goto(url); pg.wait_for_timeout(4500); pg.screenshot(path=str(SHOTS / 'demo-phone.png'))
    res['demo_hot'] = pg.evaluate("() => Array.from(FF.S.shown).map((v,i)=>[i,+v.toFixed(2)]).sort((a,b)=>b[1]-a[1]).slice(0,3)")
    pg.click('#cam'); pg.wait_for_timeout(1500); pg.screenshot(path=str(SHOTS / 'denied-phone.png'))
    res['denied_text'] = pg.text_content('#msgtext'); res['denied_shown'] = pg.is_visible('#msg'); ctx.close(); b.close()
print(json.dumps(res, indent=1))
ok = all(res[n]['source'] == 'camera' and res[n]['worst_on_slow'] and res[n]['band_glows'] and res[n]['steady_max'] < 0.25 and not res[n]['errors'] for n in ('phone', 'desktop'))
ok = ok and res['denied_shown']
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
