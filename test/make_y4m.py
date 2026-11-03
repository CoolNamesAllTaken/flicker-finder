"""Fake ceiling for Chromium's fake camera: 2 x 4 troffers, 360x640 portrait, 30 fps, 8 s.
Fixture (row 2, right) drops out at 5 Hz; fixture (row 0, left) shows uneven 120 Hz rolling-shutter
stripes; the whole frame drifts +-10 % like a camera's auto-exposure; sensor noise on top."""
import sys
import numpy as np
W, H, FPS, SECS = 360, 640, 30, 8
out = open(sys.argv[1], 'wb')
out.write(f'YUV4MPEG2 W{W} H{H} F{FPS}:1 Ip A1:1 C420jpeg\n'.encode())
rng = np.random.default_rng(1)
yy, xx = np.mgrid[0:H, 0:W]
base = np.full((H, W), 70.0)
base[(xx % 60) < 2] = 55; base[(yy % 53) < 2] = 55           # ceiling tile grid
fixtures = []
for r in range(4):
    for k in range(2):
        x0, y0 = (36 if k == 0 else 216), int(H * (0.07 + r * 0.235))
        fixtures.append((x0, y0, 108, 84))
for i in range(FPS * SECS):
    t = i / FPS
    img = base.copy()
    for n, (x0, y0, w, h) in enumerate(fixtures):
        img[y0 - 3:y0 + h + 3, x0 - 3:x0 + w + 3] = 120                 # housing
        level = 225.0
        if n == 5: level *= 1.0 if np.sin(2 * np.pi * 5 * t) > 0.1 else 0.4
        tube = np.full((h, w), level)
        if n == 0:   # uneven half-cycles: every other band darker, drifting with frame timing
            phase = (np.arange(h)[:, None] + y0) / 40.0 - t * 1.3
            tube *= 1 - 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * phase)) * (np.floor(phase * 2) % 2)
        tube[h // 2 - 2:h // 2 + 2, :] *= 0.6                            # gap between tubes
        img[y0:y0 + h, x0:x0 + w] = tube
    img *= 1 + 0.10 * np.sin(2 * np.pi * 0.4 * t)
    img += rng.normal(0, 2.5, img.shape)
    y = np.clip(img, 0, 255).astype(np.uint8)
    out.write(b'FRAME\n'); out.write(y.tobytes()); out.write(np.full((H // 2) * (W // 2) * 2, 128, np.uint8).tobytes())
out.close()
