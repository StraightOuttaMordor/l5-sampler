"""Preset beats built from the electronic kits. Installed into beats.json (marked preset=True).

    python3 -m l5sampler.presets [--home <data dir>]

Sounds are referenced by (folder, name) and resolved to library ids at install time; a preset whose
sounds are missing is skipped. Re-running replaces the old presets and leaves the user's own beats alone.
Patterns are 16 steps: 'x' = hit, '.' = rest (4 beats of 1-e-&-a).
"""
import sys
import time

from .store import Store, new_id

PRESETS = [
    ('Warehouse Techno', 128, 0, [
        ('Modular Drums', 'Kick 08', 'x...x...x...x...'),
        ('Modular Drums', 'Clap 05', '....x.......x...'),
        ('MS-20 Drums', 'Closed hat 03', '..x...x...x...x.'),
        ('Modular Perc', 'Perc Hit Short 07', '...x..x....x..x.'),
        ('Synth Perc', 'Cowbell 03', '......x.......x.'),
    ]),
    ('Electro 808', 120, 0, [
        ('TR-808', 'Kick long 02', 'x.....x...x.....'),
        ('TR-808', 'Clap 02', '....x.......x...'),
        ('TR-808', 'Hat 02', 'xxxxxxxxxxxxxxxx'),
        ('TR-808', 'Cowbell 02', '..x.....x.x.....'),
        ('TR-808', 'Rim 02', '.......x......x.'),
    ]),
    ('Deep House', 122, 20, [
        ('TR-808', 'Kick short 05', 'x...x...x...x...'),
        ('TR-808', 'Clap 02', '....x.......x...'),
        ('TR-808', 'Open hat 01', '..x...x...x...x.'),
        ('TR-808', 'Hat 03', 'x.xxx.xxx.xxx.xx'),
        ('TR-808', 'Conga hi 02', '...x..x.......x.'),
        ('TR-808', 'Conga lo 02', '......x..x......'),
    ]),
    ('Bent Breaks', 132, 15, [
        ('Circuit Bent', 'Kick 04', 'x.x.......x.....'),
        ('Circuit Bent', 'Snare 04', '....x..x.x..x..x'),
        ('Circuit Bent', 'Hat 08', 'x.x.x.x.x.x.x.x.'),
        ('Circuit Bent', 'Perc 02', '.....x.......x..'),
    ]),
    ('Boom Bap 808', 90, 35, [
        ('TR-808', 'Kick long 03', 'x......x..x.....'),
        ('TR-808', 'Snare 04', '....x.......x...'),
        ('TR-808', 'Hat 03', 'x.x.x.x.x.x.x.x.'),
        ('TR-808', 'Rim 02', '...........x..x.'),
    ]),
    ('Trap Rolls', 140, 0, [
        ('TR-808', 'Kick long 04', 'x......x..x.....'),
        ('TR-808', 'Clap 03', '........x.......'),
        ('TR-808', 'Hat 02', 'x.x.x.xxx.x.xxxx'),
        ('TR-808', 'Open hat 01', '.......x........'),
    ]),
    ('Fuzz EBM', 118, 0, [
        ('808+909 Mangled', 'Fuzz Kick 04', 'x.x.x.x.x.x.x.x.'),
        ('MS-20 Drums', 'Snare 03', '....x.......x...'),
        ('808+909 Mangled', 'Fuzz Hat closed 01', '..x...x...x...x.'),
        ('808+909 Mangled', 'Ring Clap 01', '............x..x'),
        ('808+909 Mangled', 'Fuzz Tom 01', '.......x...x....'),
    ]),
    ('Bleep Machine', 112, 10, [
        ('Synare + Syntom', 'Synare 08', 'x.....x...x.....'),
        ('Korg DS-8', 'Short 01', '....x.......x...'),
        ('Amdek', 'Short 01', '..x..x..x.....x.'),
        ('Synare + Syntom', 'Syntom 13', '.......x.x....x.'),
        ('Synth Perc', 'Chime 10', 'x...........x...'),
    ]),
    ('Kastle Glitch', 100, 25, [
        ('Drum Kastle', 'Hit 06', 'x..x....x.x.....'),
        ('Drum Kastle', 'Hit 09', '....x.......x..x'),
        ('Modular Perc', 'Perc Hit Short 12', 'x.xxx.x.x.xx.x.x'),
        ('Drum Kastle', 'Hit 18', '......x.......x.'),
        ('Weird FX', 'Percussive FX 22', '..............x.'),
    ]),
    ('Vermona Minimal', 126, 0, [
        ('Vermona DRM1', 'Vermona 17', 'x...x...x...x...'),
        ('Vermona DRM1', 'Vermona 23', '..x...x...x...xx'),
        ('Vermona DRM1', 'Vermona 03', '...x.....x....x.'),
        ('Vermona DRM1', 'Vermona 19', '....x.......x...'),
        ('Modular Perc', 'Perc Hit Short 25', '.x.....x.x......'),
    ]),
]


def build(sounds):
    """[(beat, missing)]: beats with soundIds resolved against the library."""
    idx = {(s.get('folder'), s['name']): sid for sid, s in sounds.items()}
    out = []
    now = time.time()
    for k, (name, bpm, swing, rows) in enumerate(PRESETS):
        missing = [(f, n) for f, n, _ in rows if (f, n) not in idx]
        beat = {'id': 'preset-%02d' % k, 'name': name, 'bpm': bpm, 'swing': swing, 'meter': 4, 'preset': True,
                'saved': now - k,         # newest first in the list -> presets stay in this order
                'rows': [{'soundId': idx[(f, n)], 'steps': [1 if c == 'x' else 0 for c in pat]}
                         for f, n, pat in rows if (f, n) in idx]}
        out.append((beat, missing))
    return out


def install(st):
    sounds = st.load_sounds()
    keep = [b for b in st.load_beats() if not b.get('preset')]
    got = []
    for beat, missing in build(sounds):
        if missing:
            print('skip %s: missing %s' % (beat['name'], missing))
            continue
        got.append(beat)
    # user's own beats sort above the presets (they are newer); presets keep their listed order
    base = min([b.get('saved', time.time()) for b in keep] + [time.time()]) - 1000
    for k, b in enumerate(got):
        b['saved'] = base - k
    st.save_beats(keep + got)
    print('installed %d presets (%d user beats kept)' % (len(got), len(keep)))
    return got


def main(argv):
    home = None
    if '--home' in argv:
        home = argv[argv.index('--home') + 1]
    install(Store(home) if home else Store())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
