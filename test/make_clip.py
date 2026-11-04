"""Slow-motion test clip: 2 x 4 troffers, 360x640 portrait, 240 fps, 4 s, VP8 WebM (what headless
Chromium decodes). Fixture 3 (row 1, right) sags at random moments: 10-40 % dips, 20-100 ms long,
0.1-2 s apart; the whole frame drifts +-8 % like auto-exposure; sensor noise on top.
  make_clip.py out.webm [--slowed]   --slowed: the same 960 frames timed at 30 fps, like a phone's
                                     slow-motion export that plays 8x slowed
Writes out.json with the dip times (s, real time). Needs Pillow and an ffmpeg with libvpx
(Playwright's own works: ~/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux)."""
import sys, json, io, glob, os, subprocess, pathlib, tempfile
import numpy as np
from PIL import Image
out = sys.argv[1]; slowed = '--slowed' in sys.argv
W, H, FPS, SECS = 360, 640, 240, 4
ff = os.environ.get('FFMPEG') or (sorted(glob.glob(str(pathlib.Path.home() / '.cache/ms-playwright/ffmpeg-*/ffmpeg-linux'))) or ['ffmpeg'])[-1]
rng = np.random.default_rng(5)
dips, t = [], 0.9
while True:
    t += 0.1 + 1.9 * rng.random() if dips else 0
    ln = 0.02 + 0.08 * rng.random()
    if t + ln > SECS - 0.05: break
    dips.append([round(t, 4), round(t + ln, 4), round(0.1 + 0.3 * rng.random(), 3)]); t += ln
assert len(dips) >= 2, dips
yy, xx = np.mgrid[0:H, 0:W]
base = np.full((H, W), 70.0); base[(xx % 60) < 2] = 55; base[(yy % 53) < 2] = 55
fixtures = [((36 if k == 0 else 216), int(H * (0.07 + r * 0.235)), 108, 84) for r in range(4) for k in range(2)]
tmp = tempfile.NamedTemporaryFile(suffix='.mjpg', delete=False)     # this ffmpeg has no pipe: input, so a file of JPEGs
for i in range(FPS * SECS):
    t = i / FPS
    img = base.copy()
    for n, (x0, y0, w, h) in enumerate(fixtures):
        img[y0 - 3:y0 + h + 3, x0 - 3:x0 + w + 3] = 120
        level = 225.0
        if n == 3:
            for a, b, d in dips:
                if a <= t < b: level *= 1 - d
        tube = np.full((h, w), level); tube[h // 2 - 2:h // 2 + 2, :] *= 0.6
        img[y0:y0 + h, x0:x0 + w] = tube
    img *= 1 + 0.08 * np.sin(2 * np.pi * 0.4 * t)
    img += rng.normal(0, 2.5, img.shape)
    buf = io.BytesIO(); Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGB').save(buf, 'JPEG', quality=95); tmp.write(buf.getvalue())
tmp.close()
try:
    subprocess.run([ff, '-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', str(30 if slowed else FPS), '-i', tmp.name,
                    '-c:v', 'libvpx', '-b:v', '2M' if slowed else '8M', '-qmin', '2', '-qmax', '12', '-g', '60', '-auto-alt-ref', '0', out], check=True)
finally: os.unlink(tmp.name)
json.dump({'fps': FPS, 'secs': SECS, 'slowed': slowed, 'dips': dips, 'dip_fixture': [216 + 54, int(H * (0.07 + 0.235)) + 42]}, open(os.path.splitext(out)[0] + '.json', 'w'))
print(out, len(dips), 'dips', dips)
