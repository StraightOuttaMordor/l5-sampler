# L5 Sampler: v1 spec

## Agreed in design
- **Three tabs, labeled with words:** BEAT (the home tab), SOUND, and LIBRARY. Switching takes one tap.
- **4 pads under every tab.**
  - On Beat and Sound, a pad plays its sound once.
  - On Library, you pick a sound and then tap a pad to put it there.
- **Beat tab:**
  - 16 steps in 4/4 (4 beats × 4), or 12 steps in 3/4.
  - Any number of sounds can come from the library.
  - BPM, swing, saving beats, and exporting.
  - "Play beat" / "Stop beat".
- **Sound tab:** record, trim, play, loop, name, volume, and pitch. Play and loop act on that one sound.
- **Library:** no limit on sounds. Swipe left to delete, with an "are you sure?" confirmation.
- **Leaving the Beat tab stops the beat.** It stays stopped when you come back.

## Judgment calls made during the build (open to change)
- **Step grid:** shows one sound at a time as a 4×4 grid, one row per beat, with 1-e-&-a labels and large cells. The sounds in the beat appear as chips above the grid, each with a mini pattern preview. 16 steps in a single portrait row would have made each cell about 19 px wide.
- **Recording:** tap to start and tap to stop, capped at 10 s. The silence at both ends is trimmed automatically and the sound plays right away. The mic's auto-processing is turned off so drums and other hits sound cleaner.
- **Swing:** 0–100%. At 100%, each pair of 16th notes plays 3:1 (long-short), and a small dot diagram shows the offbeat dot sliding. The labels run Straight / Light / Medium / Heavy.
- **Volume and pitch** apply wherever the sound plays (beat, pads, export). Pitch changes speed too, like the PO tape-style pitch.
- **Deleting a sound** also removes it from the pads and the current beat. The confirmation message says so.
- **Export:** a WAV of 4 loops of the beat, cut to the exact loop length so it repeats cleanly.
- **First run** includes a starter kit (synth Kick, Snare, Hat, Clap) and a starter beat, so the app makes sound immediately.
- **Storage:** everything is saved on the device (IndexedDB), and sounds are stored as WAV.

## Run
- Mac: `python3 -m http.server 8911 --bind 127.0.0.1 --directory <this dir>` + `tailscale serve --bg --https=8911 http://127.0.0.1:8911`
- Phone: open the `https://` address from `tailscale serve`. The mic only works over https or localhost.
