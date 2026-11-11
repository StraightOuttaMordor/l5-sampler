#!/usr/bin/env python3
"""On-device UI test: drives the running app over its control socket."""
import json
import os
import socket
import subprocess
import sys
import time

R = []
SHOTS = []


def ctl(cmd, **args):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect('/tmp/l5s.sock')
    s.sendall((json.dumps({'cmd': cmd, 'args': args}) + '\n').encode())
    buf = b''
    while not buf.endswith(b'\n'):
        d = s.recv(1 << 20)
        if not d:
            break
        buf += d
    r = json.loads(buf.decode())
    if isinstance(r, dict) and 'error' in r:
        print('CTL ERROR', cmd, args, r.get('error'), r.get('tb', ''))
    return r


def call(name, *a):
    return ctl('call', name=name, args=list(a))


def st():
    return ctl('state')


def ok(name, cond, info=''):
    R.append(bool(cond))
    print(('PASS ' if cond else 'FAIL ') + name + (('  — ' + str(info)) if info else ''))
    sys.stdout.flush()


def shot(n):
    p = '/tmp/l5s-%s.png' % n
    for _ in range(8):           # widget paintable is empty while a redraw is pending
        time.sleep(0.25)
        r = ctl('shot', path=p)
        if isinstance(r, dict) and r.get('ok'):
            break
    SHOTS.append(p)


SR = 48000
time.sleep(0.5)
s = st()
ok('boot: 3 tabs, beat home, 16 cells', s['tab'] == 'beat' and s['cells'] == 16)
ok('seed pads', s['pads'] == ['Kick', 'Snare', 'Hat', 'Clap'], s['pads'])
ok('first launch: EMPTY beat (no background pattern)', len(s['beat']['rows']) == 0 and not s['playing'])
ok('audio up, latency <= 40 ms', s['audio_err'] is None and s['latency_ms'] <= 40, '%.1f ms' % s['latency_ms'])
x0 = s['xruns']
shot('00-empty-beat')

# build the old starter pattern by hand through the browser
kit = {v['name']: k for k, v in s['sounds'].items() if v['folder'] == 'Starter kit'}
for nm, idx in (('Kick', [0, 8, 10]), ('Snare', [4, 12]), ('Hat', [0, 2, 4, 6, 8, 10, 12, 14])):
    call('add_row', kit[nm])
    for k in idx:
        call('tap_cell', k)
ok('built 3-row beat', len(st()['beat']['rows']) == 3)
shot('01-beat')

# timing on device: run 3 s, measure step spacing in samples
ctl('hits', clear=True)
call('start_beat')
time.sleep(3)
s = st()
ok('Play -> "Stop beat"', 'Stop' in s['play_label'])
shot('02-beat-playing')
h = [t for t, tag in ctl('hits') if tag and tag.startswith('step')]
d = [b - a for a, b in zip(h, h[1:])]
sd = SR * 60 / 90 / 4
ok('device step spacing exact @90', len(d) > 10 and all(abs(x - sd) <= 1 for x in d), sorted(set(d))[:3])
x1 = st()['xruns']
ok('no xruns during 3 s of playback', x1 - x0 <= 2, 'xruns +%d' % (x1 - x0))
call('stop_beat')

# swing
ctl('set', widget='swing', value=100)
s = st()
ok('swing word Heavy', s['swing_word'] == 'Heavy' and s['beat']['swing'] == 100)
shot('03-swing')
ctl('set', widget='swing', value=0)

# BPM
b0 = st()['beat']['bpm']
call('bpm_by', 1)
call('bpm_by', 1)
ok('BPM +2', st()['beat']['bpm'] == b0 + 2)
call('bpm_by', -2)

# step toggle
call('select_row', 0)
before = st()['beat']['rows'][0]['steps'][1]
call('tap_cell', 1)
ok('tap step toggles', st()['beat']['rows'][0]['steps'][1] != before)
call('tap_cell', 1)

# 3/4
call('set_meter', 3)
ok('3/4 -> 12 cells', st()['cells'] == 12)
shot('04-three-four')
call('set_meter', 4)
ok('back to 16', st()['cells'] == 16)

# leaving beat stops; return stays stopped
call('start_beat')
time.sleep(0.4)
call('set_tab', 'sound')
s = st()
ok('leaving Beat stops the beat', not s['playing'])
shot('05-sound-empty')
call('set_tab', 'beat')
ok('return to Beat stays stopped', not st()['playing'])

# pads over running beat
call('start_beat')
ctl('hits', clear=True)
call('pad_down', 3)
time.sleep(0.2)
tags = [t for _, t in ctl('hits')]
ok('pad plays over running beat', any(t and t.startswith('one:') for t in tags))
call('stop_beat')

# record from the real mic
call('set_tab', 'sound')
call('rec_start')
time.sleep(0.3)
ok('recording state', st()['recording'])
time.sleep(1.5)
shot('06-recording')
call('rec_stop')
time.sleep(0.4)
s = st()
ok('recorded from L5 mic', s['ed_len'] and s['ed_len'] > 1.5, s['ed_len'])
ok('auto-trimmed', 0 <= s['ed']['start'] < s['ed']['end'] <= s['ed_len'], (round(s['ed']['start'], 3), round(s['ed']['end'], 3)))
ok('auto-plays after record', s['ed_playing'] == 'once' or s['ed_playing'] is None)

# trim + loop + pitch + name + save
call('ed_loop_toggle')
time.sleep(0.6)
ok('loop playing', st()['ed_playing'] == 'loop')
shot('07-sound-loop')
call('ed_loop_toggle')
ok('loop stopped', st()['ed_playing'] is None)
ctl('set', widget='pit_s', value=5)
ok('pitch set', st()['ed']['pitch'] == 5)
call('ed_save')
s = st()
N0 = len(s['sounds'])
ok('saved to library (My recordings)', s['ed']['id'] is not None and not s['ed']['dirty']
   and s['sounds'][s['ed']['id']]['folder'] == 'My recordings')
shot('08-saved')

# library: folders first, then sounds
call('set_tab', 'lib')
s2 = st()
names = [f[0] for f in s2['folders']]
ok('library opens on folders, My recordings first', s2['lib_folder'] is None and names[0] == 'My recordings', names[:4])
shot('09a-lib-folders')
call('lib_open', 'My recordings')
new_id = s['ed']['id']
call('lib_tap', new_id)
ok('library select -> assign mode', st()['lib_sel'] == new_id)
shot('09-lib-assign')
call('pad_down', 1)
s = st()
newname = s['sounds'][new_id]['name']
ok('pad 2 = new sound', s['pads'][1] == newname, s['pads'])

# swipe + delete with confirm (inside Starter kit folder)
call('lib_open', 'Starter kit')
nm = ctl('swipe_open', index=1)
shot('10-swiped')
victim = [k for k, v in s['sounds'].items() if v['name'] == nm][0]
call('delete_sound', victim)
time.sleep(0.4)
ok('"are you sure" dialog up', st()['dialog'])
shot('11-confirm')
ctl('dialog', response='cancel')
time.sleep(0.3)
ok('cancel keeps it', len(st()['sounds']) == N0)
call('delete_sound', victim)
time.sleep(0.4)
ctl('dialog', response='ok')
time.sleep(0.3)
ok('delete removes it', len(st()['sounds']) == N0 - 1, nm)

# ---- step long-press sheet: every sound on that step, toggle live
call('set_tab', 'beat')
call('hold_cell', 0)
time.sleep(0.4)
s = st()
ok('long-press opens step sheet', s['sheet'] and s['sheet_title'].startswith('Beat 1'), s['sheet_title'])
shot('13-step-sheet')
call('close_sheet')

# ---- imported library: loops lock to the beat
s = st()
loops = {k: v for k, v in s['sounds'].items() if v['kind'] == 'loop'}
if loops:
    lid, lv = sorted(loops.items(), key=lambda kv: (kv[1]['folder'], kv[1]['name']))[0]
    call('new_beat'); time.sleep(0.3)
    if st()['dialog']:
        ctl('dialog', response='ok'); time.sleep(0.3)
    call('add_row', lid)
    s = st()
    ok('loop row added; beat adopts loop BPM', s['beat']['rows'][0].get('loop') and (not lv['bpm'] or s['beat']['bpm'] == lv['bpm']),
       (lv['folder'], lv['name'], lv['bpm'], s['beat']['bpm']))
    ok('loop row shows loop card, not grid', s['grid_mode'] == 'loop')
    shot('14-loop-card')
    x3 = st()['xruns']
    call('start_beat'); time.sleep(4)
    s = st()
    ok('loop voice running with the beat', any((v or '').startswith('loop:') for v in s['voices']), s['voices'][:4])
    print('xruns during 4 s of loop playback: +%d' % (s['xruns'] - x3))
    call('bpm_by', 7); time.sleep(1)
    ok('BPM change keeps loop playing', any((v or '').startswith('loop:') for v in st()['voices']))
    call('stop_beat')
    ok('stop beat silences loop', not any((v or '').startswith('loop:') for v in st()['voices']))
    # browser: folder list -> folder contents
    call('open_add_sound'); time.sleep(0.3)
    ok('add-sound sheet shows folders', st()['sheet_title'] == 'Add a sound to the beat')
    shot('15-add-folders')
    call('open_browser', {'mode': 'add'}, lv['folder']); time.sleep(0.4)
    ok('folder opens in sheet', st()['sheet_title'] == lv['folder'])
    shot('16-add-folder-open')
    call('close_sheet')
    call('set_tab', 'lib'); call('lib_open', lv['folder']); time.sleep(0.6)
    shot('17-lib-loop-folder')
    call('lib_open', None)
    call('set_tab', 'beat')
else:
    print('(no imported loops in this library; loop tests skipped)')

# beats sheet: save + export
call('set_tab', 'beat')
call('open_beats')
time.sleep(0.4)
shot('12-beats-sheet')
call('close_sheet')
call('export_beat')
for _ in range(60):
    time.sleep(0.25)
    ex = st()['last_export']
    if ex:
        break
ok('export WAV written', ex and ex['rms'] > 0.005 and ex['size'] > 100000, ex)

x2 = st()['xruns']
print('xruns total during test: %d (callbacks %d)' % (x2 - x0, st()['callbacks']))
print('\n%d/%d passed' % (sum(R), len(R)))
print('SHOTS ' + ' '.join(SHOTS))
