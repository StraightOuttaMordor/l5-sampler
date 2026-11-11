#!/usr/bin/env python3
"""Build a curated, phone-ready sample library from the downloaded packs.

Output: <out>/<Folder>/<Name>.wav (48k/16-bit/mono via afconvert) + manifest.json.
One level of folders. Hits grouped by machine; loops grouped by machine as "<Machine> Loops".
"""
import json
import os
import re
import subprocess
import sys

SRC = os.path.expanduser('~/.hermes/cache/scratch/packs')
OUT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '~/.hermes/cache/scratch/l5lib')
OBS = SRC + '/sampleradar-obscure-drum-machines-samples/Obscure Drum Machines'
HW = SRC + '/musicradar-hardware-drum-machine-samples/Drum Hardware'
RET = SRC + '/musicradar-retro-drum-machine-samples/musicradar-retro-drum-machine-samples'

BPM_RE = re.compile(r'\(?\s*(\d{2,3})\s*bpm\s*\)?', re.I)

# folder display names for hit dirs
HIT_DIRS = {
    OBS + '/Hits/Akai XE8': 'Akai XE8',
    OBS + '/Hits/Alesis HR-16B': 'Alesis HR-16',
    HW + '/Hits/Alesis HR-16b': 'Alesis HR-16',
    OBS + '/Hits/Boss DR-110': 'Boss DR-110',
    OBS + '/Hits/DR-220A_E': 'Boss DR-220',
    OBS + '/Hits/Dynacord P20': 'Dynacord P20',
    OBS + '/Hits/Kawai R-50E': 'Kawai R-50',
    OBS + '/Hits/Korg Superdrums': 'Korg Superdrums',
    OBS + '/Hits/Realistic Sessionmate': 'Sessionmate',
    OBS + '/Hits/Roland MC-09': 'Roland MC-09',
    OBS + '/Hits/TR 505': 'Roland TR-505',
    OBS + '/Hits/TR 707': 'Roland TR-707',
    OBS + '/Hits/Yamaha DD5': 'Yamaha DD-5',
    OBS + '/Hits/Yamaha RX11': 'Yamaha RX11',
    OBS + '/Hits/Yamaha RY8': 'Yamaha RY8',
    HW + '/Hits/Drumbrute': 'DrumBrute',
    HW + '/Hits/Jomox Airbase 99': 'Jomox Airbase',
    HW + '/Hits/Nord Drum': 'Nord Drum',
    HW + '/Hits/Roland TR-8': 'Roland TR-8',
    RET + '/Drums Hits/Raw': 'Retro Kit',
    RET + '/Drums Hits/Tape Path A': 'Retro Kit (tape)',
}
# loop dirs -> folder; obscure loops are split by machine prefix below
LOOP_DIRS = {
    HW + '/Beats/Alesis H16-B': 'Alesis HR-16 Loops',
    HW + '/Beats/DrumBrute': 'DrumBrute Loops',
    HW + '/Beats/Jomox Airbase 99': 'Jomox Loops',
    HW + '/Beats/Misc Machines': None,   # split by prefix
    HW + '/Beats/Nord Drum': 'Nord Drum Loops',
    HW + '/Beats/Roland TR-8': 'Roland TR-8 Loops',
    OBS + '/Loops/Raw': None,
    OBS + '/Loops/Processed': None,
    RET + '/Loops': 'Retro Kit Loops',
}
PREFIX_FOLDERS = [
    (r'^(boss )?dr-?110', 'Boss DR-110 Loops'), (r'^hr-?16', 'Alesis HR-16 Loops'),
    (r'^korg superdrums', 'Korg Superdrums Loops'), (r'^(roland )?mc-?09', 'Roland MC-09 Loops'),
    (r'^rx11', 'Yamaha RX11 Loops'), (r'^sessionmate', 'Sessionmate Loops'),
    (r'^tr[ -]?505', 'Roland TR-505 Loops'), (r'^(yamaha )?dd-?5', 'Yamaha DD-5 Loops'),
    (r'^mixed machines', 'Mixed Machine Loops'),
]
# retro hits: drop the dup "Analogue Chain", "Tape Path B", "WEM Copicat" variants (same kit, 5x) -> keep Raw + Tape A
# retro loops: filenames like RDM_TapeA_SR88_128-01 -> bpm from name
RETRO_BPM = re.compile(r'_(\d{2,3})-\d+$')


def clean_name(stem, folder):
    n = BPM_RE.sub('', stem).strip(' -_')
    n = re.sub(r'^RDM_', '', n)
    n = n.replace('_', ' ')
    # drop redundant machine prefix ("TR-707 Kick" in folder "Roland TR-707" -> "Kick")
    for pre in [r'^tr[- ]?\d+\s+', r'^dr[- ]?\d+\s*a?\s+', r'^xe8\s+', r'^hr-?16b?\s+', r'^p20\s+', r'^r-?50e\s+',
                r'^sessionmate\s+', r'^mc-?09\s+', r'^dd-?5\s+', r'^rx11\s+', r'^ry8\s+', r'^drumbrute\s+',
                r'^jomox\s+', r'^nord\s+', r'^alesis\s+', r'^spring verb superdrums\s+', r'^raw\s+', r'^tapea\s+']:
        if 'Loops' not in folder:
            n = re.sub(pre, '', n, flags=re.I)
    n = re.sub(r'\s+', ' ', n).strip()
    return n[:1].upper() + n[1:] if n else stem


def wavs(d):
    for dp, _, fs in os.walk(d):
        for fn in sorted(fs):
            if fn.lower().endswith('.wav') and not fn.startswith('._') and '__MACOSX' not in dp:
                yield os.path.join(dp, fn)


items = []
for d, folder in HIT_DIRS.items():
    for p in wavs(d):
        stem = os.path.basename(p)[:-4]
        items.append({'src': p, 'folder': folder, 'name': clean_name(stem, folder), 'kind': 'hit', 'bpm': None})

for d, folder in LOOP_DIRS.items():
    for p in wavs(d):
        stem = os.path.basename(p)[:-4]
        m = BPM_RE.search(stem) or RETRO_BPM.search(stem)
        bpm = int(m.group(1)) if m else None
        f = folder
        if f is None:
            low = stem.lower()
            f = next((fn for rx, fn in PREFIX_FOLDERS if re.search(rx, low)), 'Mixed Machine Loops')
        items.append({'src': p, 'folder': f, 'name': clean_name(stem, f), 'kind': 'loop', 'bpm': bpm})

# de-dup names inside a folder (case-insensitive: macOS/APFS would merge "Tr 505 01" and "TR 505 01")
seen = {}
for it in items:
    k = (it['folder'], it['name'].lower())
    seen[k] = seen.get(k, 0) + 1
    if seen[k] > 1:
        it['name'] = '%s (%d)' % (it['name'], seen[k])

os.makedirs(OUT, exist_ok=True)
man = []
for i, it in enumerate(items):
    rel = os.path.join(it['folder'], re.sub(r'[^\w\-. ()]', '_', it['name']) + '.wav')
    dst = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if True:
        r = subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16@48000', '-c', '1', '--mix', it['src'], dst],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print('FAIL', it['src'], r.stderr.strip()[:120])
            continue
    man.append({'file': rel, 'folder': it['folder'], 'name': it['name'], 'kind': it['kind'], 'bpm': it['bpm']})

with open(os.path.join(OUT, 'manifest.json'), 'w') as f:
    json.dump(man, f, indent=0)

from collections import Counter
c = Counter((m['folder'], m['kind']) for m in man)
for (fo, k), n in sorted(c.items()):
    print('%4d  %-5s %s' % (n, k, fo))
print('total', len(man), 'hits', sum(1 for m in man if m['kind'] == 'hit'), 'loops', sum(1 for m in man if m['kind'] == 'loop'),
      'no-bpm loops', sum(1 for m in man if m['kind'] == 'loop' and not m['bpm']))
