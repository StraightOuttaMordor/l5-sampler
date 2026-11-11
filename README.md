# L5 Sampler

A standalone sampler and step sequencer for the Purism Librem 5, built as a touch-friendly take on Teenage Engineering's Pocket Operator. It's a GTK4/libadwaita app that runs fully offline.

The design spec is in `SPEC.md`. The browser prototype it grew from is [l5-sampler-web](https://github.com/StraightOuttaMordor/l5-sampler-web).

## On the phone
- Open **Sampler** from the app grid. The icon is a 2×2 pad grid with an orange pad.
- Data lives in `~/.local/share/l5-sampler/`: sounds are stored as WAV, plus a small JSON library.
- Exports go to `~/Music/L5-Sampler/<beat>.wav` as 4 loops, cut so they repeat seamlessly.

## Architecture
- `l5sampler/engine.py` is a pure numpy mixer. It is sample-accurate: the sequencer schedules hits inside the audio callback in samples, and UI timers never drive audio. The same mixer renders export, so the WAV matches what you hear.
- `l5sampler/app.py` is the GTK4 + Adw UI. Pads and steps fire on touch-down, not on release.
- Audio goes through PortAudio (python3-sounddevice) via the ALSA→PulseAudio default device.
- The buffer is **768 frames (32 ms)**, measured in the live phosh session. 256 and 512 underran during playback, while 768 and 1024 ran 0 xruns over 15 s. Override with `L5S_BLOCK=`.

## Install
On the L5 itself, clone this repo and run `bash install.sh`.

To install from another computer:
```bash
L5=purism@<your-l5-ip>
scp -r l5sampler tests tools data install.sh $L5:~/.local/lib/l5-sampler/
ssh $L5 'bash ~/.local/lib/l5-sampler/install.sh'
```
One-time dependencies, already installed: `python3-numpy libportaudio2 python3-cffi python3-pip`, plus `pip3 install --user sounddevice`. For tests only: `weston grim`.

## Sample library (folders + loops)
- **The library is one level of folders.** My recordings and the Starter kit come first, then one folder per drum machine, then the "<machine> Loops" folders.
- **Loops are a special kind of sound.** Added to a beat, a loop plays the whole time the beat runs, phase-locked to the grid and varispeeded to the beat's BPM, so pitch follows tempo. An empty beat adopts the first loop's own tempo.
- **Importing samples:** `python3 -m l5sampler.importer <dir>` imports a folder of 16-bit WAVs. It reads `manifest.json` (file, folder, name, kind, bpm) if present. Otherwise each sub-folder becomes a library folder, and files named `... (120BPM).wav` become loops.
- `tools/build-library.py` builds that folder from MusicRadar's free SampleRadar drum-machine packs on a Mac (via `afconvert`). Those samples aren't redistributable, so they aren't in this repo: download them yourself.
- **Audio loads lazily** on first use, so startup costs only metadata. Startup with about 1,200 sounds takes about 6 s on the L5.

## Step editing
- Tapping a step toggles the selected sound, and every step shows a coloured dot for each sound on it.
- Long-pressing a step opens a sheet listing every sound on that step, with on/off switches that take effect live while the beat plays. It also lets you add any library sound to just that step.

## Tests
- `python3 tests/test_engine.py` runs headless on Mac or phone: timing, swing, 3/4, export, and the limiter (20 checks).
- On-device UI test (29 checks, uses the real mic and sound card, 10 screenshots to /tmp):
  `HEADLESS=1 bash tools/run-test.sh && sleep 9 && python3 tests/test_device.py; bash tools/stop-test.sh`
  `HEADLESS=1` runs a private headless weston, so the test works with the phone's screen locked.
- `tools/bench-live.sh` measures xruns per buffer size in the live session (the screen must be on).

## Gotchas
- Never `pkill -f <pattern>` over ssh. It matches the ssh command line itself and drops the session. Use the pidfiles (`tools/stop-test.sh`).
- PyGObject 3.40 can't wrap GskRenderNode, so `ctl_shot` renders via ctypes.
