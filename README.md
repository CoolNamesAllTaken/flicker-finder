# Flicker Finder

Find the flickering light with your phone camera: a fluorescent fixture, an LED that PWM-dims, or a desk lamp that sags whenever a heater next to it switches.

**Open:** https://coolnamesalltaken.github.io/flicker-finder/

Point the phone at the lights. The flickering one glows on a heatmap. Tap a spot for its brightness trace, score, frequency and a strip of recent dips.

- Slow flicker (1–15 Hz dropouts, strobing): frame-to-frame brightness per grid cell.
- Sudden dips and spikes, with or without a rhythm (a lamp sagging when a heater, motor or rework station switches): each frame against the cell's own recent median, in units of its own scatter (median absolute deviation), plus single dark bands or steps the rolling shutter catches inside one frame. Cells that had one get a small diamond.
- Fast flicker (100 Hz to kHz PWM): rolling-shutter stripes, also measured on full-resolution line strips, with the stripe frequency where it can be estimated. Needs a short exposure, which Android Chrome can lock (the chip shows 1/N). iOS Safari stays on auto.
- Hold (chip with the hill icon): heat rises at once and fades over 2–60 s, so a brief event stays visible.

Every frame the camera delivers is analyzed with its own timestamp (MediaStreamTrackProcessor or requestVideoFrameCallback), at the highest frame rate the camera offers; the number on the camera button is the measured rate.

**Slow-motion clips** (clip button) are the best way to catch short dips, and the way to get high-rate analysis on iPhone: a 240 fps clip is played slowed down (or stepped frame by frame on a slow phone) so every frame is analyzed at its real timing. If the clip was exported slowed (240 fps shown at 30), tap the clip chip at the top to say how much (⅛).

<img src="docs/screenshot.png" width="300">

## Limits

- A dip shorter than about one exposure, or falling between frames, can be missed: at 30 fps a 5 ms dip is seen only if it overlaps an exposure; at 240 fps nearly everything over ~5 ms shows. The rolling shutter helps: a dip during readout shows as a band in that one frame.
- PWM stripes need an exposure shorter than one PWM period (1/4000 s catches up to ~3 kHz). On auto exposure (iOS, most desktop browsers) fast PWM averages out.
- PWM at an exact multiple of the frame rate makes stripes stand still; they look like a fixed pattern and are ignored.
- The stripe frequency assumes the sensor reads one frame in one frame time; real sensors take 0.5–1× of it, so treat it as rough (right within a factor of two).
- A dip that hits the whole picture at once (all lights on the same sagging circuit) looks like the camera re-exposing and is not credited to any one spot.

## Tests

Need Playwright for Python (Chromium headless shell), numpy and Pillow.

- `test/unit.py`: synthetic frames through the page's analyzer: the original 4 Hz + banding case; a lamp with random dips (10–40 %, 20–100 ms, 0.1–2 s apart, rolling shutter, jittered frame times) at 30 and 60 fps; 1 kHz and 2.5 kHz PWM stripes on a 1080×1920 video through the app's own grab path.
- `test/make_y4m.py test/ceiling.y4m` + `test/fakecam.py`: the page against Chromium's fake camera.
- `test/make_clip.py test/clip240.webm` (and `test/clip240-slowed.webm --slowed`) + `test/clip.py`: 240 fps slow-motion clips with random dips through the clip button.
