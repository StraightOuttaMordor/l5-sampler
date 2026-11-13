#!/usr/bin/env python3
"""Build the phone-ready ELECTRONIC library (v2) from six MusicRadar SampleRadar packs.

Packs (download + unzip into ~/.cache/l5packs, see references in the skill):
  musicradar-808-samples, 808 and 909 Reimagined, Modular Percussion, Micro Modulars,
  Synth Percussion, musicradar-glitch-kit-samples
One-shot HITS only (no loops / beats). Output: <out>/<Folder>/<Name>.wav (48k/16/mono via afconvert)
+ manifest.json, for `python3 -m l5sampler.importer <out>`.
Royalty-free but NO redistribution: never commit the samples.
"""
import json
import os
import re
import subprocess
import sys
import wave
from collections import Counter

SRC = os.path.expanduser('~/.cache/l5packs')
OUT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '~/.hermes/cache/scratch/l5elec')
MAX_S = 5.0          # longer one-shots are drones/textures, useless on a 16-step grid

# (source dir relative to SRC, library folder)
DIRS = [
    ('musicradar-808-samples/Hits', 'TR-808'),
    ('808 and 909 Reimagined/Hits', '808+909 Mangled'),
    ('Modular Percussion/MS20 semi modular drum Hits', 'MS-20 Drums'),
    ('Modular Percussion/Modular Drum Hits', 'Modular Drums'),
    ('Modular Percussion/Modular Percussion Hits', 'Modular Perc'),
    ('Synth Percussion/Modular', 'Modular Perc'),
    ('Modular Percussion/Percussive FX', 'Weird FX'),
    ('musicradar-glitch-kit-samples/Glitch FX', 'Weird FX'),
    ('Micro Modulars/Bastl Kastle/FX Single shots', 'Weird FX'),
    ('Micro Modulars/Volca Modular/Single shots', 'Weird FX'),
    ('musicradar-glitch-kit-samples/Bent Hits', 'Circuit Bent'),
    ('musicradar-glitch-kit-samples/Circuit Bent', 'Circuit Bent'),
    ('Micro Modulars/Bastl Drum kastle/Drum Hits', 'Drum Kastle'),
    ('Synth Percussion/Synare 3', 'Synare + Syntom'),
    ('Synth Percussion/Syntom', 'Synare + Syntom'),
    ('Synth Percussion/Amdek Perc Synth', 'Amdek'),
    ('Synth Percussion/DS8 Clone', 'Korg DS-8'),
    ('Synth Percussion/Vermona DRM1', 'Vermona DRM1'),
    ('Synth Percussion/Nord drum', 'Nord Drum'),
    ('Synth Percussion/Misc Synth perc', 'Synth Perc'),
    ('Synth Percussion/Synth Cowbell', 'Synth Perc'),
    ('Synth Percussion/Synchime', 'Synth Perc'),
]
BPM_RE = re.compile(r'\(?\s*\d{2,3}\s*bpm\s*\)?', re.I)
E808 = {'BD': 'Kick', 'SD': 'Snare', 'CH': 'Hat', 'OH': 'Open hat', 'CP': 'Clap', 'CB': 'Cowbell', 'CY': 'Cymbal',
        'MA': 'Maracas', 'RS': 'Rim', 'CL': 'Claves', 'HC': 'Conga hi', 'MC': 'Conga mid', 'LC': 'Conga lo',
        'LT': 'Tom lo', 'MT': 'Tom mid', 'HT': 'Tom hi'}
TRI = {'FuzzPedals': 'Fuzz', 'HogRing': 'Ring', 'KDFX': 'KDFX', 'QuantAlias': 'Alias'}


def clean(stem):
    m = re.match(r'E808_([A-Z]{2})(?:\[(\w+)\])?-(\d+)$', stem)
    if m:
        return ' '.join(x for x in (E808[m.group(1)], m.group(2), m.group(3)) if x)
    m = re.match(r'TReImag_([A-Za-z]+)_([A-Za-z]+)(?:_(\d+))?$', stem)
    if m:
        what = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', m.group(2)).capitalize()
        return ' '.join(x for x in (TRI.get(m.group(1), m.group(1)), what, m.group(3)) if x)
    n = re.sub(r'^(Ms20|Modular|Bent|DS8|Drum Kastle|Amdek|Misc|Modular Perc) ', '', stem)
    n = n.replace('ClosedHat', 'Closed hat').replace('OpenHat', 'Open hat').replace('Hit short', 'Hit Short')
    n = re.sub(r'\s+', ' ', n.replace('_', ' ')).strip()
    return n[:1].upper() + n[1:]


def dur(p):
    try:
        with wave.open(p) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        r = subprocess.run(['afinfo', p], capture_output=True, text=True).stdout
        m = re.search(r'estimated duration: ([\d.]+)', r)
        return float(m.group(1)) if m else 0.0


items, dropped = [], Counter()
for rel, folder in DIRS:
    for dp, _, fs in os.walk(os.path.join(SRC, rel)):
        for fn in sorted(fs):
            if not fn.lower().endswith('.wav') or fn.startswith('._'):
                continue
            stem = fn[:-4]
            if BPM_RE.search(stem):
                dropped['loop'] += 1
                continue
            p = os.path.join(dp, fn)
            if dur(p) > MAX_S:
                dropped['too long'] += 1
                continue
            items.append({'src': p, 'folder': folder, 'name': clean(stem)})

seen = Counter()
for it in items:
    k = (it['folder'], it['name'].lower())
    seen[k] += 1
    if seen[k] > 1:
        it['name'] = '%s (%d)' % (it['name'], seen[k])

os.makedirs(OUT, exist_ok=True)
man = []
for it in items:
    rel = os.path.join(it['folder'], re.sub(r'[^\w\-. ()+]', '_', it['name']) + '.wav')
    dst = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    r = subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16@48000', '-c', '1', '--mix', it['src'], dst],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print('FAIL', it['src'], r.stderr.strip()[:120])
        continue
    man.append({'file': rel, 'folder': it['folder'], 'name': it['name'], 'kind': 'hit', 'bpm': None})

with open(os.path.join(OUT, 'manifest.json'), 'w') as f:
    json.dump(man, f, indent=0)
for fo, n in sorted(Counter(m['folder'] for m in man).items()):
    print('%4d  %s' % (n, fo))
print('total', len(man), 'dropped', dict(dropped))
