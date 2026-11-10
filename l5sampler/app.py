"""L5 Sampler: native GTK4 / libadwaita app for the Librem 5.

Three tabs (BEAT / SOUND / LIBRARY), 4 pads always on screen, offline.
"""
import json
import os
import re
import socket
import threading
import time

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

import numpy as np  # noqa: E402

from . import engine as E  # noqa: E402
from .kit import starter_kit  # noqa: E402
from .store import Store, new_id  # noqa: E402

COLORS = ['#ff5a1f', '#2f6bff', '#141414', '#d9a000', '#00a676', '#a64dff', '#e0457b', '#0a9db0']
COUNT = ['', 'e', '&', 'a']
EXPORT_DIR = os.path.expanduser('~/Music/L5-Sampler')
MAX_REC_S = 10.0

CSS = """
window, .root { background: #ebe8e1; color: #141414; }
.page { padding: 10px 12px 6px 12px; }
.lbl { font-size: 11px; font-weight: 800; letter-spacing: 1px; color: #6f6a61; }
.dim { color: #6f6a61; font-size: 12px; }
button.b, button.b:hover { background: #f7f5f0; background-image: none; box-shadow: none; border: none;
  border-radius: 12px; min-height: 44px; font-weight: 700; padding: 0 12px; color: #141414; }
button.b:active { background: #e3dfd6; }
button.b.primary { background: #141414; color: #fff; }
button.b.primary.on { background: #ff5a1f; }
button.b.accent { background: #ff5a1f; color: #fff; }
button.b.ghost { background: transparent; border: 1.5px solid #d3cec4; }
button.b.dark { background: #141414; color: #fff; }
button.b.rec { background: #141414; color: #fff; min-height: 54px; font-size: 16px; }
button.b.rec.live { background: #d92d20; }
button.b:disabled { opacity: 0.55; }
.stepper { background: #f7f5f0; border-radius: 12px; }
.stepbtn { min-width: 36px; min-height: 50px; font-size: 22px; font-weight: 600; }
.stepbtn:active { background: #e3dfd6; border-radius: 12px; }
.bpmval { font-size: 20px; font-weight: 800; }
.bpmcap { font-size: 9px; font-weight: 800; color: #6f6a61; letter-spacing: 1px; }
.seg { background: #f7f5f0; border-radius: 12px; padding: 3px; }
.seg button { background: transparent; background-image: none; box-shadow: none; border: none; border-radius: 9px;
  font-weight: 800; color: #6f6a61; min-width: 40px; padding: 0 6px; }
.seg button:checked { background: #141414; color: #fff; }
.card { background: #f7f5f0; border-radius: 12px; padding: 4px 12px; }
.chip { background: #f7f5f0; border-radius: 12px; padding: 6px 10px 6px 8px; min-width: 76px; }
.chip.sel { background: #141414; color: #fff; }
.chip .n { font-weight: 800; font-size: 13px; }
.chip.add { background: transparent; border: 1.5px dashed #d3cec4; color: #6f6a61; font-weight: 800; padding: 0 12px; }
.strip { min-width: 4px; border-radius: 2px; }
.cell { background: #f7f5f0; border-radius: 12px; }
.cell.beat1 { background: #e1ddd3; }
.cell label { font-size: 12px; font-weight: 800; color: #57534b; margin: 6px 0 0 8px; }
.cell.on label { color: rgba(255,255,255,0.85); }
.cell.ph { box-shadow: inset 0 0 0 3px #141414; }
.wave { background: #ffffff; border-radius: 14px; }
entry.name { background: #f7f5f0; border: none; box-shadow: none; border-radius: 12px; min-height: 44px; font-weight: 700; }
.lrow-back { background: #d92d20; border-radius: 12px; }
.lrow-back button { background: transparent; background-image: none; box-shadow: none; border: none; color: #fff; font-weight: 800; min-width: 96px; }
.lrow-front { background: #f7f5f0; border-radius: 12px; padding: 8px 8px 8px 10px; }
.lrow-front.sel { background: #141414; color: #fff; }
.lrow-front .ln { font-weight: 800; }
.lrow-front.sel .dim { color: #bbb; }
button.edit { background: transparent; background-image: none; box-shadow: none; border: 1.5px solid #d3cec4; border-radius: 10px;
  min-height: 36px; font-weight: 700; font-size: 13px; padding: 0 12px; color: inherit; }
.padbar { border-top: 1px solid #d3cec4; padding: 6px 12px; }
.pad { background: #141414; color: #fff; border-radius: 14px; padding: 6px 9px; min-height: 58px; }
.pad .pn { font-size: 10px; font-weight: 800; letter-spacing: 1px; color: rgba(255,255,255,0.7); }
.pad .ps { font-size: 13px; font-weight: 800; }
.pad.empty { background: #f7f5f0; color: #6f6a61; border: 1.5px dashed #d3cec4; }
.pad.empty .pn { color: #6f6a61; }
.pad.assign { background: transparent; color: #ff5a1f; border: 2px dashed #ff5a1f; }
.pad.assign .pn { color: #ff5a1f; }
.pad.hit { background: #ff5a1f; color: #fff; }
.padhint { color: #ff5a1f; font-weight: 700; font-size: 13px; }
.tabbar { background: #f7f5f0; }
.tabbar button { background: transparent; background-image: none; box-shadow: none; border: none; border-radius: 0;
  min-height: 50px; font-weight: 800; font-size: 14px; letter-spacing: 1px; color: #6f6a61; border-top: 3px solid transparent; }
.tabbar button.on { color: #141414; border-top: 3px solid #ff5a1f; }
.scrim { background: rgba(0,0,0,0.35); }
.sheet { background: #ebe8e1; border-radius: 18px 18px 0 0; padding: 12px 14px 22px 14px; }
.sheet .title { font-size: 18px; font-weight: 800; }
.shitem { background: #f7f5f0; border-radius: 12px; padding: 6px 6px 6px 12px; min-height: 50px; }
.shitem.cur { box-shadow: inset 0 0 0 2px #ff5a1f; }
.shitem.dis { opacity: 0.4; }
.shitem .t { font-weight: 800; }
button.x { background: transparent; background-image: none; box-shadow: none; border: none; color: #d92d20; font-weight: 800; font-size: 18px; min-width: 42px; }
""" + ''.join('.c%d, .cell.on.c%d { background: %s; }\n' % (i, i, c) for i, c in enumerate(COLORS))


def hbox(sp=0, *css):
    b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=sp)
    for c in css:
        b.add_css_class(c)
    return b


def vbox(sp=0, *css):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=sp)
    for c in css:
        b.add_css_class(c)
    return b


def label(text, *css, xalign=None, ellipsize=False, wrap=False):
    lb = Gtk.Label(label=text)
    for c in css:
        lb.add_css_class(c)
    if xalign is not None:
        lb.set_xalign(xalign)
    if ellipsize:
        from gi.repository import Pango
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if wrap:
        lb.set_wrap(True)
    return lb


def button(text, *css, cb=None):
    b = Gtk.Button(label=text)
    b.add_css_class('b')
    for c in css:
        b.add_css_class(c)
    if cb:
        b.connect('clicked', lambda *_: cb())
    return b


def on_press(widget, cb, release=None):
    """React on touch-DOWN (instruments must not wait for release)."""
    g = Gtk.GestureClick()
    g.connect('pressed', lambda g, n, x, y: cb())
    if release:
        g.connect('released', lambda g, n, x, y: release())
        g.connect('stopped', lambda g: release())
    widget.add_controller(g)
    return g


def fmt_s(s):
    return ('%.2f s' % s) if s < 10 else ('%.1f s' % s)


def new_beat():
    return {'id': None, 'name': 'Untitled beat', 'bpm': 90, 'swing': 0, 'meter': 4, 'rows': []}


class SamplerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='org.wingman.L5Sampler', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.win = None
        self.connect('activate', self.on_activate)
        self.connect('shutdown', self.on_shutdown)

    # ================================================================ model
    def load_model(self):
        self.store = Store()
        if self.store.fresh:
            self.seed()
        self.sounds = self.store.load_sounds()
        for s in self.sounds.values():
            self.prep(s)
        st = self.store.load_state()
        self.beat = st.get('draft') or new_beat()
        self.dirty = bool(st.get('dirty', False))
        pads = (st.get('pads') or [None] * 4) + [None] * 4
        self.pads = [p if p in self.sounds else None for p in pads[:4]]
        self.beats = self.store.load_beats()
        self.clean_beat()
        self.sel = 0
        self.tab = 'beat'
        self.lib_sel = None
        self.playing = False
        self.cur_step = -1
        self.ed = self.empty_ed()
        self.recording = False
        self.rec_t0 = 0.0
        self.open_row = None
        self._save_src = None
        self._toast = None
        self._dlg = None
        self._tick_src = None
        self.engine = E.Engine()
        self.io = None
        self.audio_err = None
        try:
            self.io = E.AudioIO(self.engine, device=os.environ.get('L5S_DEVICE') or None,
                                blocksize=int(os.environ.get('L5S_BLOCK', '768')),   # 768 = 32 ms: measured xrun-free under phosh; 256/512 underrun while playing
                                latency=float(os.environ['L5S_LATENCY']) if os.environ.get('L5S_LATENCY') else 'low')
        except Exception as e:  # keep the UI usable even with no sound card
            self.audio_err = str(e)
        self.push_pattern()

    def seed(self):
        sounds = {}
        ids = []
        for k, (name, data) in enumerate(starter_kit()):
            sid = new_id()
            s = {'id': sid, 'name': name, 'data': data, 'start': 0.0, 'end': len(data) / E.SR,
                 'vol': 1.0, 'pitch': 0, 'created': time.time() - (10 - k)}
            sounds[sid] = s
            self.store.save_sound(sounds, s, True)
            ids.append(sid)

        def st(idx):
            a = [0] * 16
            for i in idx:
                a[i] = 1
            return a
        beat = new_beat()
        beat['name'] = 'Starter beat'
        beat['rows'] = [{'soundId': ids[0], 'steps': st([0, 8, 10])},
                        {'soundId': ids[1], 'steps': st([4, 12])},
                        {'soundId': ids[2], 'steps': st([0, 2, 4, 6, 8, 10, 12, 14])}]
        self.store.save_state({'draft': beat, 'dirty': True, 'pads': ids[:4]})

    def prep(self, s):
        s['buf'] = E.render_sound(s['data'], s['start'], s['end'], s['pitch'])

    def steps(self):
        return 12 if self.beat['meter'] == 3 else 16

    def clean_beat(self):
        self.beat['rows'] = [r for r in self.beat['rows'] if r['soundId'] in self.sounds]
        self.sel = max(0, min(getattr(self, 'sel', 0), len(self.beat['rows']) - 1))

    def push_pattern(self):
        n = self.steps()
        rows = []
        for r in self.beat['rows']:
            s = self.sounds.get(r['soundId'])
            if s:
                rows.append((s['buf'], float(s['vol']), tuple(r['steps'][:n])))
        self.engine.pattern = E.Pattern(self.beat['bpm'], float(self.beat['swing']), n, rows)

    def persist(self):
        if self._save_src:
            GLib.source_remove(self._save_src)

        def go():
            self._save_src = None
            self.store.save_state({'draft': self.beat, 'dirty': self.dirty, 'pads': self.pads})
            return False
        self._save_src = GLib.timeout_add(300, go)

    def beat_changed(self):
        self.dirty = True
        self.push_pattern()
        self.persist()

    def sound_len(self, s):
        return (s['end'] - s['start']) / (2.0 ** (s['pitch'] / 12.0))

    def play_sound(self, sid):
        s = self.sounds.get(sid)
        if s:
            self.engine.play(s['buf'], float(s['vol']), tag='one:' + sid)

    # ================================================================ build UI
    def on_activate(self, app):
        if self.win:
            self.win.present()
            return
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.load_model()
        self.win = Adw.ApplicationWindow(application=self, title='Sampler')
        self.win.set_default_size(360, 720)
        self.win.add_css_class('root')

        self.layer = Gtk.Overlay()
        main = vbox(0)
        self.layer.set_child(main)

        self.stack = Gtk.Stack()
        self.stack.add_named(self.build_beat(), 'beat')
        self.stack.add_named(self.build_sound(), 'sound')
        self.stack.add_named(self.build_lib(), 'lib')
        self.toasts = Adw.ToastOverlay()     # toasts float above the pads, never over the tabs
        self.toasts.set_child(self.stack)
        self.toasts.set_vexpand(True)
        main.append(self.toasts)
        main.append(self.build_pads())
        main.append(self.build_tabs())
        self.build_sheet()

        self.win.set_content(self.layer)
        self.win.present()
        self.render_beat()
        self.render_pads()
        self.render_sound()
        if self.audio_err:
            self.toast('No audio output: ' + self.audio_err[:60])
        if os.environ.get('L5S_CTL'):
            self.start_ctl(os.environ['L5S_CTL'])

    def on_shutdown(self, app):
        try:
            if self._save_src:
                GLib.source_remove(self._save_src)
            self.store.save_state({'draft': self.beat, 'dirty': self.dirty, 'pads': self.pads})
        except Exception:
            pass
        if self.io:
            if self.recording:
                self.io.rec_stop()
            self.io.close()

    # ---------------------------------------------------------------- BEAT
    def build_beat(self):
        page = vbox(8, 'page')
        top = hbox(8)
        self.play_btn = button('▶  Play beat', 'primary', cb=self.toggle_beat)
        self.play_btn.set_hexpand(True)
        top.append(self.play_btn)

        stepper = hbox(0, 'stepper')
        minus = label('−', 'stepbtn')
        plus = label('+', 'stepbtn')
        self.hold_repeat(minus, -1)
        self.hold_repeat(plus, 1)
        mid = vbox(0)
        mid.set_valign(Gtk.Align.CENTER)
        self.bpm_lbl = label('90', 'bpmval')
        mid.append(self.bpm_lbl)
        mid.append(label('BPM', 'bpmcap'))
        mid.set_size_request(40, -1)
        stepper.append(minus)
        stepper.append(mid)
        stepper.append(plus)
        top.append(stepper)

        seg = hbox(3, 'seg')
        self.m4 = Gtk.ToggleButton(label='4/4')
        self.m3 = Gtk.ToggleButton(label='3/4')
        self.m3.set_group(self.m4)
        self.m4.connect('toggled', lambda b: b.get_active() and self.set_meter(4))
        self.m3.connect('toggled', lambda b: b.get_active() and self.set_meter(3))
        seg.append(self.m4)
        seg.append(self.m3)
        top.append(seg)
        page.append(top)

        sw = hbox(10, 'card')
        sw.set_size_request(-1, 46)
        sw.append(label('SWING', 'lbl'))
        self.swing = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.swing.set_draw_value(False)
        self.swing.set_hexpand(True)
        self.swing.connect('value-changed', self.on_swing)
        sw.append(self.swing)
        self.swing_viz = Gtk.DrawingArea()
        self.swing_viz.set_size_request(58, 20)
        self.swing_viz.set_valign(Gtk.Align.CENTER)
        self.swing_viz.set_draw_func(self.draw_swing)
        sw.append(self.swing_viz)
        self.swing_word = label('Straight', xalign=1)
        self.swing_word.set_size_request(62, -1)
        sw.append(self.swing_word)
        page.append(sw)

        self.chips_sc = Gtk.ScrolledWindow()
        self.chips_sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.chips_sc.set_size_request(-1, 56)
        self.chips = hbox(6)
        self.chips_sc.set_child(self.chips)
        page.append(self.chips_sc)

        self.grid = Gtk.Grid()
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_spacing(6)
        self.grid.set_column_spacing(6)
        self.grid.set_vexpand(True)
        self.cells = []
        self.cells_n = 0
        page.append(self.grid)

        bot = hbox(6)
        self.clear_btn = button('Clear', 'ghost', cb=self.clear_row)
        self.remove_btn = button('Remove', 'ghost', cb=self.remove_row)
        self.beats_btn = button('Starter beat ▾', cb=self.open_beats)
        self.beats_btn.set_hexpand(True)
        self.beats_btn.get_child().set_ellipsize(3) if isinstance(self.beats_btn.get_child(), Gtk.Label) else None
        bot.append(self.clear_btn)
        bot.append(self.remove_btn)
        bot.append(self.beats_btn)
        page.append(bot)
        return page

    def hold_repeat(self, w, d):
        st = {'t1': None, 't2': None}

        def stop():
            for k in ('t1', 't2'):
                if st[k]:
                    GLib.source_remove(st[k])
                    st[k] = None

        def rep():
            self.bpm_by(d)
            return True

        def start_rep():
            st['t1'] = None
            st['t2'] = GLib.timeout_add(70, rep)
            return False

        def press():
            stop()
            self.bpm_by(d)
            st['t1'] = GLib.timeout_add(400, start_rep)
        on_press(w, press, stop)

    def bpm_by(self, d):
        self.beat['bpm'] = max(40, min(220, self.beat['bpm'] + d))
        self.beat_changed()
        self.render_beat_top()

    def set_meter(self, m):
        if self.beat['meter'] == m:
            return
        self.beat['meter'] = m
        self.beat_changed()
        self.render_beat()

    def on_swing(self, sc):
        if getattr(self, '_quiet', False):
            return
        self.beat['swing'] = int(sc.get_value())
        self.beat_changed()
        self.render_beat_top()

    def draw_swing(self, area, cr, w, h, *a):
        gap = 7.0
        sh = (self.beat['swing'] / 100.0) * 0.5 * gap
        cr.set_source_rgb(0.83, 0.81, 0.77)
        cr.set_line_width(1.5)
        cr.move_to(1, h / 2)
        cr.line_to(w - 1, h / 2)
        cr.stroke()
        for i in range(8):
            x = 4 + i * gap + (sh if i % 2 else 0)
            if i % 2:
                cr.set_source_rgb(1.0, 0.353, 0.122)
            else:
                cr.set_source_rgb(0.08, 0.08, 0.08)
            cr.arc(x, h / 2, 3.6 if i % 4 == 0 else 2.6, 0, 6.3)
            cr.fill()

    def render_beat_top(self):
        b = self.beat
        self.play_btn.set_label('■  Stop beat' if self.playing else '▶  Play beat')
        if self.playing:
            self.play_btn.add_css_class('on')
        else:
            self.play_btn.remove_css_class('on')
        self.bpm_lbl.set_label(str(b['bpm']))
        self._quiet = True
        (self.m4 if b['meter'] == 4 else self.m3).set_active(True)
        self.swing.set_value(b['swing'])
        self._quiet = False
        s = b['swing']
        self.swing_word.set_label('Straight' if s < 8 else 'Light' if s < 36 else 'Medium' if s < 76 else 'Heavy')
        self.swing_viz.queue_draw()
        self.beats_btn.set_label(('• ' if self.dirty else '') + b['name'] + ' ▾')
        lb = self.beats_btn.get_child()
        if isinstance(lb, Gtk.Label):
            from gi.repository import Pango
            lb.set_ellipsize(Pango.EllipsizeMode.END)

    def render_chips(self):
        c = self.chips.get_first_child()
        while c:
            nx = c.get_next_sibling()
            self.chips.remove(c)
            c = nx
        n = self.steps()
        self.chip_widgets = []
        if not self.beat['rows']:
            note = label('No sounds in this beat yet →', 'dim')
            self.chips.append(note)
        for i, r in enumerate(self.beat['rows']):
            s = self.sounds.get(r['soundId'])
            chip = hbox(8, 'chip')
            if i == self.sel:
                chip.add_css_class('sel')
            strip = Gtk.Box()
            strip.add_css_class('strip')
            strip.add_css_class('c%d' % (i % len(COLORS)))
            chip.append(strip)
            col = vbox(4)
            col.set_valign(Gtk.Align.CENTER)
            nl = label(s['name'], 'n', xalign=0, ellipsize=True)
            nl.set_max_width_chars(12)
            col.append(nl)
            dots = Gtk.DrawingArea()
            dots.set_size_request(n * 5 + 9, 6)
            dots.set_draw_func(self.draw_dots, (i, n))
            col.append(dots)
            chip.append(col)
            on_press(chip, lambda i=i: self.select_row(i))
            self.chips.append(chip)
            self.chip_widgets.append(chip)
        add = hbox(0, 'chip', 'add')
        add.append(label('+ Add sound'))
        on_press(add, self.open_add_sound)
        self.chips.append(add)
        has = bool(self.beat['rows'])
        self.clear_btn.set_sensitive(has)
        self.remove_btn.set_sensitive(has)

    def draw_dots(self, area, cr, w, h, data):
        i, n = data
        if i >= len(self.beat['rows']):
            return
        r = self.beat['rows'][i]
        col = Gdk.RGBA()
        col.parse(COLORS[i % len(COLORS)])
        sel = i == self.sel
        x = 0
        for k in range(n):
            if k and k % 4 == 0:
                x += 3
            if r['steps'][k]:
                cr.set_source_rgba(col.red, col.green, col.blue, 1)
            elif sel:
                cr.set_source_rgb(0.27, 0.27, 0.27)
            else:
                cr.set_source_rgb(0.83, 0.81, 0.77)
            cr.rectangle(x, 0, 4, h)
            cr.fill()
            x += 5

    def select_row(self, i):
        self.sel = i
        self.render_chips()
        self.render_grid()
        if not self.playing:
            self.play_sound(self.beat['rows'][i]['soundId'])

    def render_grid(self):
        n = self.steps()
        if self.cells_n != n:
            for cw in self.cells:
                self.grid.remove(cw)
            self.cells = []
            for k in range(n):
                cell = Gtk.Box()
                cell.add_css_class('cell')
                cell.set_hexpand(True)
                cell.set_vexpand(True)
                lb = label(str(k // 4 + 1) if k % 4 == 0 else COUNT[k % 4], xalign=0)
                lb.set_valign(Gtk.Align.START)
                cell.append(lb)
                on_press(cell, lambda k=k: self.tap_cell(k))
                self.grid.attach(cell, k % 4, k // 4, 1, 1)
                self.cells.append(cell)
            self.cells_n = n
        row = self.beat['rows'][self.sel] if self.beat['rows'] else None
        cc = 'c%d' % (self.sel % len(COLORS))
        for k, cell in enumerate(self.cells):
            for c in ['c%d' % j for j in range(len(COLORS))] + ['on']:
                cell.remove_css_class(c)
            if k % 4 == 0:
                cell.add_css_class('beat1')
            if row and row['steps'][k]:
                cell.add_css_class('on')
                cell.add_css_class(cc)
        self.draw_playhead()

    def tap_cell(self, k):
        if not self.beat['rows']:
            self.open_add_sound()
            return
        r = self.beat['rows'][self.sel]
        r['steps'][k] = 0 if r['steps'][k] else 1
        if r['steps'][k] and not self.playing:
            self.play_sound(r['soundId'])
        self.beat_changed()
        self.render_grid()
        for chip in getattr(self, 'chip_widgets', []):
            pass
        self.render_chips()
        self.render_beat_top()

    def draw_playhead(self):
        for k, cell in enumerate(self.cells):
            if k == self.cur_step:
                cell.add_css_class('ph')
            else:
                cell.remove_css_class('ph')

    def render_beat(self):
        self.render_beat_top()
        self.render_chips()
        self.render_grid()

    def toggle_beat(self):
        if self.playing:
            self.stop_beat()
        else:
            self.start_beat()

    def start_beat(self):
        if not self.beat['rows']:
            self.toast('Add a sound to the beat first')
            return
        self.push_pattern()
        self.engine.seq_start()
        self.playing = True
        self.render_beat_top()
        self.ensure_tick()

    def stop_beat(self):
        if not self.playing:
            return
        self.engine.seq_stop()
        self.playing = False
        self.cur_step = -1
        self.draw_playhead()
        self.render_beat_top()

    def clear_row(self):
        if not self.beat['rows']:
            return
        self.beat['rows'][self.sel]['steps'] = [0] * 16
        self.beat_changed()
        self.render_beat()

    def remove_row(self):
        if not self.beat['rows']:
            return
        r = self.beat['rows'][self.sel]
        s = self.sounds[r['soundId']]

        def go():
            self.beat['rows'].pop(self.sel)
            self.sel = max(0, min(self.sel, len(self.beat['rows']) - 1))
            self.beat_changed()
            self.render_beat()
            if not self.beat['rows']:
                self.stop_beat()
        if any(r['steps']):
            self.confirm('Remove “%s” from this beat?' % s['name'], 'It stays in your library.', 'Remove', go)
        else:
            go()

    def open_add_sound(self):
        used = set(r['soundId'] for r in self.beat['rows'])
        body = vbox(6)
        allx = sorted(self.sounds.values(), key=lambda s: -s['created'])
        if not allx:
            body.append(label('Library is empty.', 'dim'))
        for s in allx:
            dis = s['id'] in used
            it = hbox(8, 'shitem')
            if dis:
                it.add_css_class('dis')
            col = vbox(2)
            col.set_hexpand(True)
            col.set_valign(Gtk.Align.CENTER)
            col.append(label(s['name'], 't', xalign=0, ellipsize=True))
            col.append(label('already in this beat' if dis else fmt_s(self.sound_len(s)), 'dim', xalign=0))
            it.append(col)
            if not dis:
                on_press(it, lambda sid=s['id']: self.add_row(sid))
            body.append(it)
        rec = button('●  Record a new sound', 'ghost', cb=lambda: (self.close_sheet(), self.set_tab('sound')))
        rec.set_margin_top(6)
        body.append(rec)
        self.open_sheet('Add a sound to the beat', body)

    def add_row(self, sid):
        self.beat['rows'].append({'soundId': sid, 'steps': [0] * 16})
        self.sel = len(self.beat['rows']) - 1
        self.beat_changed()
        self.close_sheet()
        self.render_beat()
        self.play_sound(sid)

    # ---- beats sheet (save / load / new / export)
    def open_beats(self):
        body = vbox(8)
        name = Gtk.Entry()
        name.add_css_class('name')
        name.set_text(self.beat['name'])
        name.set_max_length(40)

        def on_name(e):
            self.beat['name'] = e.get_text() or 'Untitled beat'
            self.beat_changed()
            self.render_beat_top()
        name.connect('changed', on_name)
        body.append(name)
        r1 = hbox(8)
        sv = button('Save', 'primary', cb=lambda: self.save_beat(False, name))
        sa = button('Save as new', cb=lambda: self.save_beat(True, name))
        sv.set_hexpand(True)
        sa.set_hexpand(True)
        r1.append(sv)
        r1.append(sa)
        body.append(r1)
        r2 = hbox(8)
        nb = button('New beat', 'ghost', cb=self.new_beat)
        ex = button('⤓ Export WAV', 'ghost', cb=self.export_beat)
        nb.set_hexpand(True)
        ex.set_hexpand(True)
        r2.append(nb)
        r2.append(ex)
        body.append(r2)
        lb = label('SAVED BEATS', 'lbl', xalign=0)
        lb.set_margin_top(8)
        body.append(lb)
        self.beats_list = vbox(6)
        body.append(self.beats_list)
        self.fill_beats()
        self.open_sheet('Beats', body)

    def fill_beats(self):
        c = self.beats_list.get_first_child()
        while c:
            nx = c.get_next_sibling()
            self.beats_list.remove(c)
            c = nx
        bs = sorted(self.beats, key=lambda b: -b.get('saved', 0))
        if not bs:
            self.beats_list.append(label('No saved beats yet.', 'dim'))
        for bt in bs:
            it = hbox(8, 'shitem')
            if bt['id'] == self.beat.get('id'):
                it.add_css_class('cur')
            col = vbox(2)
            col.set_hexpand(True)
            col.set_valign(Gtk.Align.CENTER)
            col.append(label(bt['name'], 't', xalign=0, ellipsize=True))
            col.append(label('%d BPM · %d/4 · %d sounds' % (bt['bpm'], bt['meter'], len(bt['rows'])), 'dim', xalign=0))
            on_press(col, lambda bt=bt: self.load_beat(bt))
            it.append(col)
            x = Gtk.Button(label='✕')
            x.add_css_class('x')
            x.connect('clicked', lambda *_, bt=bt: self.delete_beat(bt))
            it.append(x)
            self.beats_list.append(it)

    def save_beat(self, as_new, entry):
        if as_new or not self.beat.get('id'):
            if as_new and self.beat.get('id'):
                self.beat['name'] += ' copy'
            self.beat['id'] = new_id()
        snap = json.loads(json.dumps(self.beat))
        snap['saved'] = time.time()
        self.beats = [b for b in self.beats if b['id'] != snap['id']] + [snap]
        self.store.save_beats(self.beats)
        self.dirty = False
        self.persist()
        self.render_beat_top()
        entry.set_text(self.beat['name'])
        self.toast('Saved “%s”' % self.beat['name'])
        self.fill_beats()

    def load_beat(self, bt):
        def go():
            self.stop_beat()
            self.beat = json.loads(json.dumps(bt))
            self.beat.pop('saved', None)
            self.clean_beat()
            self.sel = 0
            self.dirty = False
            self.push_pattern()
            self.persist()
            self.close_sheet()
            self.render_beat()
            self.toast('Loaded “%s”' % bt['name'])
        if self.dirty:
            self.confirm('Load “%s”?' % bt['name'], 'Unsaved changes to the current beat will be lost.', 'Load', go)
        else:
            go()

    def delete_beat(self, bt):
        def go():
            self.beats = [b for b in self.beats if b['id'] != bt['id']]
            self.store.save_beats(self.beats)
            if self.beat.get('id') == bt['id']:
                self.beat['id'] = None
                self.dirty = True
                self.persist()
                self.render_beat_top()
            self.fill_beats()
        self.confirm('Delete the beat “%s”?' % bt['name'], 'This can’t be undone.', 'Delete', go, danger=True)

    def new_beat(self):
        def go():
            self.stop_beat()
            keep = (self.beat['bpm'], self.beat['meter'])
            self.beat = new_beat()
            self.beat['bpm'], self.beat['meter'] = keep
            self.sel = 0
            self.dirty = False
            self.push_pattern()
            self.persist()
            self.close_sheet()
            self.render_beat()
        if self.dirty:
            self.confirm('Start a new beat?', 'Unsaved changes will be lost.', 'New beat', go)
        else:
            go()

    def export_beat(self):
        if not self.beat['rows']:
            self.toast('Nothing to export yet')
            return
        self.push_pattern()
        pat = self.engine.pattern
        name = re.sub(r'[^\w\- ]+', '', self.beat['name']).strip().replace(' ', '-') or 'beat'
        os.makedirs(EXPORT_DIR, exist_ok=True)
        path = os.path.join(EXPORT_DIR, name + '.wav')
        self.toast('Rendering…')

        def work():
            y = E.offline_render(pat, loops=4)
            E.write_wav(path, y, stereo=True)
            rms = float(np.sqrt(np.mean(y * y)))
            self.last_export = {'path': path, 'seconds': len(y) / E.SR, 'rms': rms, 'size': os.path.getsize(path)}
            GLib.idle_add(lambda: self.toast('Exported to Music/L5-Sampler/%s.wav' % name) and False)
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- SOUND
    def empty_ed(self):
        return {'id': None, 'data': None, 'start': 0.0, 'end': 0.0, 'name': '', 'vol': 1.0, 'pitch': 0,
                'dirty': False, 'buf': None, 'pk': None, 'pkw': 0}

    def build_sound(self):
        page = vbox(8, 'page')
        head = hbox(8)
        self.name_e = Gtk.Entry()
        self.name_e.add_css_class('name')
        self.name_e.set_placeholder_text('Name this sound')
        self.name_e.set_max_length(40)
        self.name_e.set_hexpand(True)
        self.name_e.connect('changed', self.on_name)
        head.append(self.name_e)
        head.append(button('New', 'ghost', cb=self.ed_new))
        page.append(head)

        self.wave = Gtk.DrawingArea()
        self.wave.add_css_class('wave')
        self.wave.set_vexpand(True)
        self.wave.set_size_request(-1, 110)
        self.wave.set_draw_func(self.draw_wave)
        drag = Gtk.GestureDrag()
        drag.connect('drag-begin', self.trim_begin)
        drag.connect('drag-update', self.trim_update)
        drag.connect('drag-end', self.trim_end)
        self.wave.add_controller(drag)
        self.trim_drag = None
        page.append(self.wave)

        info = hbox(0)
        self.trim_info = label('', 'dim', xalign=0)
        self.trim_info.set_hexpand(True)
        self.trim_len = label('', 'dim', xalign=1)
        info.append(self.trim_info)
        info.append(self.trim_len)
        page.append(info)

        r = hbox(8)
        self.play_b = button('▶  Play', cb=self.ed_play_toggle)
        self.loop_b = button('⟲  Loop', cb=self.ed_loop_toggle)
        self.play_b.set_hexpand(True)
        self.loop_b.set_hexpand(True)
        r.append(self.play_b)
        r.append(self.loop_b)
        page.append(r)

        self.rec_b = button('●  Record', 'rec', cb=self.rec_toggle)
        page.append(self.rec_b)

        card = vbox(0, 'card')
        self.vol_s, self.vol_v = self.slider(card, 'Volume', 0, 150, self.on_vol)
        self.pit_s, self.pit_v = self.slider(card, 'Pitch', -12, 12, self.on_pitch)
        page.append(card)

        self.save_b = button('Save to library', 'accent', cb=self.ed_save)
        page.append(self.save_b)
        return page

    def slider(self, parent, name, lo, hi, cb):
        row = hbox(10)
        row.set_size_request(-1, 40)
        lb = label(name, xalign=0)
        lb.set_size_request(58, -1)
        row.append(lb)
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
        sc.set_draw_value(False)
        sc.set_hexpand(True)
        sc.connect('value-changed', cb)
        row.append(sc)
        v = label('', xalign=1)
        v.set_size_request(48, -1)
        row.append(v)
        parent.append(row)
        return sc, v

    def ed_rebuild(self):
        ed = self.ed
        if ed['data'] is not None:
            ed['buf'] = E.render_sound(ed['data'], ed['start'], ed['end'], ed['pitch'])

    def ed_load(self, sid):
        s = self.sounds[sid]
        self.ed_stop()
        self.ed = self.empty_ed()
        self.ed.update({'id': sid, 'data': s['data'], 'start': s['start'], 'end': s['end'], 'name': s['name'],
                        'vol': s['vol'], 'pitch': s['pitch']})
        self.ed_rebuild()
        self.render_sound()

    def ed_new(self):
        def go():
            self.ed_stop()
            self.ed = self.empty_ed()
            self.render_sound()
        if self.ed['dirty']:
            self.confirm('Discard this unsaved sound?', None, 'Discard', go, danger=True)
        else:
            go()

    def ed_play(self, loop):
        if self.ed['buf'] is None:
            return
        self.engine.play(self.ed['buf'], float(self.ed['vol']), tag='preview', loop=loop)
        self.ed_playing = 'loop' if loop else 'once'
        self.render_sound_btns()
        self.ensure_tick()

    def ed_stop(self):
        self.engine.stop_tag('preview')
        self.ed_playing = None
        if hasattr(self, 'play_b'):
            self.render_sound_btns()

    def ed_play_toggle(self):
        if getattr(self, 'ed_playing', None) == 'once':
            self.ed_stop()
        else:
            self.ed_play(False)

    def ed_loop_toggle(self):
        if getattr(self, 'ed_playing', None) == 'loop':
            self.ed_stop()
        else:
            self.ed_play(True)

    def ed_changed(self, rebuild=True):
        self.ed['dirty'] = True
        if rebuild:
            self.ed_rebuild()
            if getattr(self, 'ed_playing', None):
                self.engine.update_tag('preview', self.ed['buf'], float(self.ed['vol']))
        self.render_sound()

    def on_name(self, e):
        if getattr(self, '_quiet', False):
            return
        self.ed['name'] = e.get_text()
        self.ed['dirty'] = True
        self.render_save_btn()

    def on_vol(self, sc):
        if getattr(self, '_quiet', False):
            return
        self.ed['vol'] = sc.get_value() / 100.0
        self.ed['dirty'] = True
        if getattr(self, 'ed_playing', None):
            self.engine.update_tag('preview', self.ed['buf'], float(self.ed['vol']))
        self.render_sound()

    def on_pitch(self, sc):
        if getattr(self, '_quiet', False):
            return
        self.ed['pitch'] = int(sc.get_value())
        self.ed_changed()

    # ---- recording
    def rec_toggle(self):
        if self.recording:
            self.rec_stop()
        else:
            self.rec_start()

    def rec_start(self):
        if not self.io:
            self.toast('No audio device')
            return

        def go():
            self.ed_stop()
            try:
                self.io.rec_start()
            except Exception as e:
                self.toast('Mic error: %s' % str(e)[:60])
                return
            self.recording = True
            self.rec_t0 = time.time()
            self.render_sound()
            self.ensure_tick()
        if self.ed['dirty']:
            self.confirm('Record over the unsaved sound?', None, 'Record', go)
        else:
            go()

    def rec_stop(self):
        if not self.recording:
            return
        self.recording = False
        data = self.io.rec_stop()
        if len(data) < E.SR * 0.05:
            self.toast('Recording too short')
            self.render_sound()
            return
        a, b = E.auto_trim(data)
        name = self.ed['name'] if self.ed['id'] is None else ''
        self.ed = self.empty_ed()
        self.ed.update({'data': data, 'start': a, 'end': b, 'name': name, 'dirty': True})
        self.ed_rebuild()
        self.render_sound()
        self.ed_play(False)

    # ---- trim drag
    def trim_begin(self, g, x, y):
        if self.ed['data'] is None or self.recording:
            g.set_state(Gtk.EventSequenceState.DENIED)
            return
        g.set_state(Gtk.EventSequenceState.CLAIMED)
        w = self.wave.get_width()
        dur = len(self.ed['data']) / E.SR
        t = x / w * dur
        self.trim_drag = ('start' if abs(t - self.ed['start']) <= abs(t - self.ed['end']) else 'end', x)
        self.trim_move(x)

    def trim_update(self, g, dx, dy):
        if self.trim_drag:
            self.trim_move(self.trim_drag[1] + dx)

    def trim_end(self, g, dx, dy):
        if not self.trim_drag:
            return
        self.trim_drag = None
        self.ed_changed(rebuild=True)
        if getattr(self, 'ed_playing', None) is None:
            self.ed_play(False)

    def trim_move(self, x):
        w = self.wave.get_width()
        dur = len(self.ed['data']) / E.SR
        t = max(0.0, min(dur, x / w * dur))
        if self.trim_drag[0] == 'start':
            self.ed['start'] = min(t, self.ed['end'] - 0.02)
        else:
            self.ed['end'] = max(t, self.ed['start'] + 0.02)
        self.ed['dirty'] = True
        self.render_sound(light=True)

    def draw_wave(self, area, cr, W, H, *a):
        ed = self.ed
        if self.recording and self.io:
            lv = list(self.io.rec_level)[-int(W / 3):]
            top = 30
            mid = top + (H - top) / 2.0
            cr.set_source_rgb(0.85, 0.18, 0.13)
            for i, v in enumerate(lv):
                h = max(2, v * (H - top - 8))
                cr.rectangle(i * 3, mid - h / 2, 2, h)
            cr.fill()
            cr.set_source_rgb(0.43, 0.42, 0.38)
            cr.select_font_face('Sans', 0, 1)
            cr.set_font_size(12)
            cr.move_to(10, 18)
            cr.show_text('Recording… tap Stop when done (max %d s)' % MAX_REC_S)
            return
        if ed['data'] is None:
            cr.set_source_rgb(0.43, 0.42, 0.38)
            cr.select_font_face('Sans', 0, 1)
            cr.set_font_size(14)
            txt = 'Tap Record to capture a sound'
            ext = cr.text_extents(txt)
            cr.move_to((W - ext.width) / 2, H / 2)
            cr.show_text(txt)
            return
        if ed['pk'] is None or ed['pkw'] != W:
            ed['pk'] = E.peaks(ed['data'], int(W))
            ed['pkw'] = W
        dur = len(ed['data']) / E.SR
        xa, xb = ed['start'] / dur * W, ed['end'] / dur * W
        pk = ed['pk']
        cr.set_line_width(1)
        for inside in (False, True):
            if inside:
                cr.set_source_rgb(0.08, 0.08, 0.08)
            else:
                cr.set_source_rgb(0.79, 0.77, 0.73)
            for x in range(len(pk)):
                if (xa <= x <= xb) != inside:
                    continue
                h = max(1.0, pk[x] * (H - 16))
                cr.rectangle(x, H / 2 - h / 2, 1, h)
            cr.fill()
        cr.set_source_rgba(0.92, 0.91, 0.88, 0.55)
        cr.rectangle(0, 0, xa, H)
        cr.rectangle(xb, 0, W - xb, H)
        cr.fill()
        for x in (xa, xb):
            cx = max(12, min(W - 12, x))
            cr.set_source_rgb(1.0, 0.353, 0.122)
            cr.rectangle(x - 1.5, 0, 3, H)
            cr.fill()
            cr.arc(cx, H - 15, 11, 0, 6.3)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.rectangle(cx - 3.5, H - 19, 1.5, 8)
            cr.rectangle(cx + 2, H - 19, 1.5, 8)
            cr.fill()
        pr = self.engine.tag_progress('preview')
        if pr and self.io:
            pos, L, loop = pr
            pos = max(0, pos - int(self.io.latency_s * E.SR))
            rate = 2.0 ** (ed['pitch'] / 12.0)
            t = ed['start'] + (pos % max(1, L) if loop else min(pos, L)) * rate / E.SR
            cr.set_source_rgb(0.18, 0.42, 1.0)
            cr.rectangle(t / dur * W - 1, 0, 2, H)
            cr.fill()

    def render_sound_btns(self):
        has = self.ed['data'] is not None
        p = getattr(self, 'ed_playing', None)
        self.play_b.set_sensitive(has and not self.recording)
        self.loop_b.set_sensitive(has and not self.recording)
        self.play_b.set_label('■  Stop' if p == 'once' else '▶  Play')
        self.loop_b.set_label('■  Stop loop' if p == 'loop' else '⟲  Loop')
        if p == 'loop':
            self.loop_b.add_css_class('dark')
        else:
            self.loop_b.remove_css_class('dark')

    def render_save_btn(self):
        ed = self.ed
        has = ed['data'] is not None
        self.save_b.set_sensitive(has and not self.recording and (ed['id'] is None or ed['dirty']))
        self.save_b.set_label('Save to library' if ed['id'] is None else ('Save changes' if ed['dirty'] else 'Saved ✓'))

    def render_sound(self, light=False):
        ed = self.ed
        has = ed['data'] is not None
        self.trim_info.set_label('Drag the orange handles to trim' if has else '')
        self.trim_len.set_label(fmt_s((ed['end'] - ed['start']) / (2.0 ** (ed['pitch'] / 12.0))) if has else '')
        self.wave.queue_draw()
        self.render_save_btn()
        if light:
            return
        self._quiet = True
        if self.name_e.get_text() != ed['name']:
            self.name_e.set_text(ed['name'])
        self.vol_s.set_value(round(ed['vol'] * 100))
        self.pit_s.set_value(ed['pitch'])
        self._quiet = False
        self.vol_v.set_label('%d%%' % round(ed['vol'] * 100))
        self.pit_v.set_label('%+d st' % ed['pitch'] if ed['pitch'] else '0 st')
        for w in (self.vol_s, self.pit_s, self.name_e):
            w.set_sensitive(has and not self.recording)
        if self.recording:
            self.rec_b.set_label('■  Stop · %.1f s' % (time.time() - self.rec_t0))
            self.rec_b.add_css_class('live')
        else:
            self.rec_b.set_label('●  Record again' if has else '●  Record')
            self.rec_b.remove_css_class('live')
        self.render_sound_btns()

    def ed_save(self):
        ed = self.ed
        if ed['data'] is None:
            return
        is_new = ed['id'] is None
        sid = ed['id'] or new_id()
        name = ed['name'].strip() or 'Sound %d' % (len(self.sounds) + 1)
        s = {'id': sid, 'name': name, 'data': ed['data'], 'start': ed['start'], 'end': ed['end'],
             'vol': ed['vol'], 'pitch': ed['pitch'],
             'created': time.time() if is_new else self.sounds[sid]['created']}
        self.prep(s)
        self.sounds[sid] = s
        self.store.save_sound(self.sounds, s, write_audio=is_new)
        ed.update({'id': sid, 'name': name, 'dirty': False})
        self.push_pattern()
        self.render_sound()
        self.render_pads()
        self.toast('“%s” saved to library' % name if is_new else 'Changes saved')

    # ---------------------------------------------------------------- LIBRARY
    def build_lib(self):
        page = vbox(8, 'page')
        h = hbox(8)
        h.append(label('Library', xalign=0))
        h.get_first_child().add_css_class('title-3')
        self.lib_count = label('', 'dim', xalign=0)
        self.lib_count.set_valign(Gtk.Align.BASELINE)
        h.append(self.lib_count)
        page.append(h)
        page.append(label('Tap a sound to hear it and pick it up. Then tap a pad to put it there. '
                          'Swipe left to delete.', 'dim', xalign=0, wrap=True))
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_vexpand(True)
        self.lib_list = vbox(6)
        sc.set_child(self.lib_list)
        page.append(sc)
        return page

    def render_lib(self):
        c = self.lib_list.get_first_child()
        while c:
            nx = c.get_next_sibling()
            self.lib_list.remove(c)
            c = nx
        self.open_row = None
        self.lib_rows = {}
        allx = sorted(self.sounds.values(), key=lambda s: -s['created'])
        self.lib_count.set_label('%d sound%s' % (len(allx), '' if len(allx) == 1 else 's'))
        if not allx:
            self.lib_list.append(label('No sounds yet. Record one on the Sound tab.', 'dim'))
        for s in allx:
            self.lib_list.append(self.lib_row(s))
        self.render_pads()

    def lib_row(self, s):
        sid = s['id']
        ov = Gtk.Overlay()
        back = hbox(0, 'lrow-back')
        back.set_size_request(-1, 58)
        sp = Gtk.Box()
        sp.set_hexpand(True)
        back.append(sp)
        dl = Gtk.Button(label='Delete')
        dl.connect('clicked', lambda *_: self.delete_sound(sid))
        back.append(dl)
        back.set_opacity(0)          # hidden until a swipe starts (no red bleed at the corners)
        ov.set_child(back)

        front = hbox(10, 'lrow-front')
        if self.lib_sel == sid:
            front.add_css_class('sel')
        thumb = Gtk.DrawingArea()
        thumb.set_size_request(56, 30)
        thumb.set_valign(Gtk.Align.CENTER)
        thumb.set_draw_func(self.draw_thumb, sid)
        front.append(thumb)
        col = vbox(2)
        col.set_hexpand(True)
        col.set_valign(Gtk.Align.CENTER)
        col.append(label(s['name'], 'ln', xalign=0, ellipsize=True))
        on = [str(i + 1) for i, p in enumerate(self.pads) if p == sid]
        col.append(label(fmt_s(self.sound_len(s)) + (' · Pad ' + ', '.join(on) if on else ''), 'dim', xalign=0))
        front.append(col)
        ed = Gtk.Button(label='Edit')
        ed.add_css_class('edit')
        ed.set_valign(Gtk.Align.CENTER)
        ed.connect('clicked', lambda *_: self.lib_edit(sid))
        front.append(ed)
        ov.add_overlay(front)

        st = {'mode': None, 'base': 0, 'dx': 0}

        def begin(g, x, y):
            st['mode'] = 'maybe'
            st['base'] = 96 if self.open_row is front else 0
            st['x'], st['y'] = x, y

        def update(g, dx, dy):
            if st['mode'] == 'maybe':
                if abs(dx) > 8 and abs(dx) > abs(dy):
                    st['mode'] = 'swipe'
                    g.set_state(Gtk.EventSequenceState.CLAIMED)
                elif abs(dy) > 8:
                    st['mode'] = None
                    g.set_state(Gtk.EventSequenceState.DENIED)
            if st['mode'] == 'swipe':
                st['dx'] = max(0, min(110, st['base'] - dx))
                back.set_opacity(1)
                front.set_margin_end(int(st['dx']))

        def end(g, dx, dy):
            if st['mode'] == 'swipe':
                opened = st['dx'] > 48
                front.set_margin_end(96 if opened else 0)
                back.set_opacity(1 if opened else 0)
                if opened:
                    self.close_open_row(except_=front)
                    self.open_row = front
                elif self.open_row is front:
                    self.open_row = None
            elif st['mode'] == 'maybe':
                hit = front.pick(st['x'] + dx, st['y'] + dy, Gtk.PickFlags.DEFAULT)
                w = hit
                while w is not None and w is not front:
                    if w is ed:
                        st['mode'] = None
                        return
                    w = w.get_parent()
                if self.open_row:
                    self.close_open_row()
                else:
                    self.lib_tap(sid)
            st['mode'] = None
        drag = Gtk.GestureDrag()
        drag.connect('drag-begin', begin)
        drag.connect('drag-update', update)
        drag.connect('drag-end', end)
        front.add_controller(drag)
        self.lib_rows[sid] = front
        return ov

    def close_open_row(self, except_=None):
        if self.open_row is not None and self.open_row is not except_:
            self.open_row.set_margin_end(0)
            self.open_row.get_parent().get_child().set_opacity(0)
        if except_ is None:
            self.open_row = None

    def draw_thumb(self, area, cr, w, h, sid):
        s = self.sounds.get(sid)
        if not s:
            return
        pk = E.peaks(s['data'], w)
        dur = len(s['data']) / E.SR
        a, z = s['start'] / dur * w, s['end'] / dur * w
        sel = self.lib_sel == sid
        for x in range(w):
            alpha = 1.0 if a <= x <= z else 0.25
            if sel:
                cr.set_source_rgba(1, 1, 1, alpha)
            else:
                cr.set_source_rgba(0.08, 0.08, 0.08, alpha)
            hh = max(2.0, pk[x] * h)
            cr.rectangle(x, h / 2 - hh / 2, 1, hh)
            cr.fill()

    def lib_tap(self, sid):
        self.lib_sel = None if self.lib_sel == sid else sid
        if self.lib_sel:
            self.play_sound(sid)
        self.render_lib()

    def lib_edit(self, sid):
        if self.open_row:
            self.close_open_row()
            return

        def go():
            self.ed_load(sid)
            self.set_tab('sound')
        if self.ed['dirty'] and self.ed['id'] != sid:
            self.confirm('Discard the unsaved sound on the Sound tab?', None, 'Discard', go, danger=True)
        else:
            go()

    def delete_sound(self, sid):
        s = self.sounds[sid]
        uses = []
        if sid in self.pads:
            uses.append('pads')
        if any(r['soundId'] == sid for r in self.beat['rows']):
            uses.append('the current beat')
        body = 'Are you sure?' + (' It will also be removed from %s.' % ' and '.join(uses) if uses else '') + \
            ' This can’t be undone.'

        def go():
            del self.sounds[sid]
            self.store.delete_sound(self.sounds, sid)
            self.pads = [None if p == sid else p for p in self.pads]
            had = len(self.beat['rows'])
            self.clean_beat()
            if len(self.beat['rows']) != had:
                self.beat_changed()
            if not self.beat['rows']:
                self.stop_beat()
            if self.ed['id'] == sid:
                self.ed_stop()
                self.ed = self.empty_ed()
                self.render_sound()
            if self.lib_sel == sid:
                self.lib_sel = None
            self.push_pattern()
            self.persist()
            self.render_lib()
            self.render_beat()
            self.toast('Deleted “%s”' % s['name'])
        self.confirm('Delete “%s”?' % s['name'], body, 'Delete', go, danger=True, on_cancel=self.close_open_row)

    # ---------------------------------------------------------------- PADS + TABS
    def build_pads(self):
        box = vbox(0)
        self.pad_hint = Gtk.Revealer()
        self.pad_hint_l = label('', 'padhint')
        self.pad_hint_l.set_margin_top(4)
        self.pad_hint.set_child(self.pad_hint_l)
        box.append(self.pad_hint)
        bar = hbox(6, 'padbar')
        bar.set_homogeneous(True)
        self.pad_w = []
        for i in range(4):
            p = vbox(0, 'pad')
            pn = label('PAD %d' % (i + 1), 'pn', xalign=0)
            ps = label('', 'ps', xalign=0, ellipsize=True)
            ps.set_vexpand(True)
            ps.set_valign(Gtk.Align.END)
            p.append(pn)
            p.append(ps)
            on_press(p, lambda i=i: self.pad_down(i))
            bar.append(p)
            self.pad_w.append((p, pn, ps))
        box.append(bar)
        return box

    def render_pads(self):
        assigning = self.tab == 'lib' and self.lib_sel is not None
        for i, (p, pn, ps) in enumerate(self.pad_w):
            sid = self.pads[i]
            s = self.sounds.get(sid) if sid else None
            for c in ('empty', 'assign'):
                p.remove_css_class(c)
            if assigning:
                p.add_css_class('assign')
            elif not s:
                p.add_css_class('empty')
            pn.set_label(('PUT ON %d' if assigning else 'PAD %d') % (i + 1))
            ps.set_label(s['name'] if s else 'empty')
        if assigning:
            self.pad_hint_l.set_label('Tap a pad to put “%s” there' % self.sounds[self.lib_sel]['name'])
        self.pad_hint.set_reveal_child(assigning)

    def pad_down(self, i):
        if self.tab == 'lib' and self.lib_sel:
            self.pads[i] = self.lib_sel
            n = self.sounds[self.lib_sel]['name']
            self.lib_sel = None
            self.persist()
            self.render_lib()
            self.toast('“%s” → Pad %d' % (n, i + 1))
            return
        sid = self.pads[i]
        if not sid or sid not in self.sounds:
            self.toast('Empty pad. Assign a sound in Library')
            return
        self.play_sound(sid)
        p = self.pad_w[i][0]
        p.add_css_class('hit')
        GLib.timeout_add(110, lambda: p.remove_css_class('hit') or False)

    def build_tabs(self):
        bar = hbox(0, 'tabbar')
        bar.set_homogeneous(True)
        self.tab_b = {}
        for key, txt in (('beat', 'BEAT'), ('sound', 'SOUND'), ('lib', 'LIBRARY')):
            b = Gtk.Button(label=txt)
            b.connect('clicked', lambda *_, k=key: self.set_tab(k))
            bar.append(b)
            self.tab_b[key] = b
        self.tab_b['beat'].add_css_class('on')
        return bar

    def set_tab(self, t):
        if t == self.tab:
            return
        if self.tab == 'beat':
            self.stop_beat()            # leaving Beat stops the beat; it stays stopped on return
        if self.tab == 'sound':
            self.ed_stop()
            self.rec_stop()
        if t != 'lib':
            self.lib_sel = None
        self.tab = t
        if self._toast:
            self._toast.dismiss()
        self.stack.set_visible_child_name(t)
        for k, b in self.tab_b.items():
            if k == t:
                b.add_css_class('on')
            else:
                b.remove_css_class('on')
        if t == 'beat':
            self.render_beat()
        elif t == 'sound':
            self.render_sound()
        else:
            self.render_lib()
        self.render_pads()

    # ---------------------------------------------------------------- sheet / dialog / toast
    def build_sheet(self):
        self.sheet_layer = Gtk.Overlay()
        scrim = Gtk.Box()
        scrim.add_css_class('scrim')
        scrim.set_hexpand(True)
        scrim.set_vexpand(True)
        on_press(scrim, self.close_sheet)
        self.sheet_layer.set_child(scrim)
        self.sheet_rev = Gtk.Revealer()
        self.sheet_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.sheet_rev.set_transition_duration(180)
        self.sheet_rev.set_valign(Gtk.Align.END)
        sheet = vbox(8, 'sheet')
        head = hbox(8)
        self.sheet_title = label('', 'title', xalign=0)
        self.sheet_title.set_hexpand(True)
        head.append(self.sheet_title)
        done = Gtk.Button(label='Done')
        done.add_css_class('flat')
        done.connect('clicked', lambda *_: self.close_sheet())
        head.append(done)
        sheet.append(head)
        self.sheet_sc = Gtk.ScrolledWindow()
        self.sheet_sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sheet_sc.set_propagate_natural_height(True)
        self.sheet_sc.set_max_content_height(500)
        sheet.append(self.sheet_sc)
        self.sheet_rev.set_child(sheet)
        self.sheet_layer.add_overlay(self.sheet_rev)
        self.sheet_layer.set_visible(False)
        self.layer.add_overlay(self.sheet_layer)

    def open_sheet(self, title, body):
        self.sheet_title.set_label(title)
        self.sheet_sc.set_child(body)
        self.sheet_layer.set_visible(True)
        self.sheet_rev.set_reveal_child(True)

    def close_sheet(self):
        self.sheet_rev.set_reveal_child(False)
        GLib.timeout_add(200, lambda: (self.sheet_layer.set_visible(self.sheet_rev.get_reveal_child())) and False)

    def confirm(self, heading, body, ok, cb, danger=False, on_cancel=None):
        d = Adw.MessageDialog.new(self.win, heading, body)
        d.add_response('cancel', 'Cancel')
        d.add_response('ok', ok)
        d.set_response_appearance('ok', Adw.ResponseAppearance.DESTRUCTIVE if danger
                                  else Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response('cancel')
        d.set_close_response('cancel')

        def resp(dlg, r):
            self._dlg = None
            if r == 'ok':
                cb()
            elif on_cancel:
                on_cancel()
        d.connect('response', resp)
        self._dlg = d
        d.present()

    def toast(self, msg):
        if self._toast:
            self._toast.dismiss()
        t = Adw.Toast.new(msg)
        t.set_timeout(2)
        self._toast = t
        self.toasts.add_toast(t)
        self.last_toast = msg

    # ---------------------------------------------------------------- animation tick
    def ensure_tick(self):
        if self._tick_src is None:
            self._tick_src = GLib.timeout_add(16, self.tick)

    def tick(self):
        busy = False
        if self.playing and self.io:
            busy = True
            audible = self.engine.t - int(self.io.latency_s * E.SR)
            log = self.engine.step_log
            changed = False
            while log and log[0][0] <= audible:
                self.cur_step = log.popleft()[1]
                changed = True
            if changed:
                self.draw_playhead()
        if self.recording:
            busy = True
            el = time.time() - self.rec_t0
            self.rec_b.set_label('■  Stop · %.1f s' % el)
            self.wave.queue_draw()
            if el >= MAX_REC_S:
                self.rec_stop()
        if getattr(self, 'ed_playing', None):
            pr = self.engine.tag_progress('preview')
            if pr is None:
                self.ed_playing = None
                self.render_sound_btns()
            else:
                busy = True
            self.wave.queue_draw()
        if not busy:
            self._tick_src = None
            return False
        return True

    # ---------------------------------------------------------------- test control socket
    def start_ctl(self, path):
        try:
            os.unlink(path)
        except OSError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        srv.listen(4)

        def serve():
            while True:
                conn, _ = srv.accept()
                try:
                    req = json.loads(conn.makefile().readline())
                    ev = threading.Event()
                    box = {}

                    def run():
                        try:
                            box['r'] = getattr(self, 'ctl_' + req['cmd'])(**req.get('args', {}))
                        except Exception as e:
                            import traceback
                            box['r'] = {'error': repr(e), 'tb': traceback.format_exc()}
                        ev.set()
                        return False
                    GLib.idle_add(run)
                    ev.wait(10)
                    conn.sendall((json.dumps(box.get('r'), default=str) + '\n').encode())
                except Exception as e:
                    try:
                        conn.sendall((json.dumps({'error': repr(e)}) + '\n').encode())
                    except Exception:
                        pass
                finally:
                    conn.close()
        threading.Thread(target=serve, daemon=True).start()

    def ctl_state(self):
        return {'tab': self.tab, 'playing': self.playing, 'beat': self.beat, 'dirty': self.dirty, 'sel': self.sel,
                'pads': [self.sounds[p]['name'] if p in self.sounds else None for p in self.pads],
                'sounds': {k: {kk: v[kk] for kk in ('name', 'start', 'end', 'vol', 'pitch')} for k, v in self.sounds.items()},
                'ed': {k: self.ed[k] for k in ('id', 'start', 'end', 'name', 'vol', 'pitch', 'dirty')},
                'ed_len': None if self.ed['data'] is None else len(self.ed['data']) / E.SR,
                'ed_playing': getattr(self, 'ed_playing', None), 'recording': self.recording,
                'cells': len(self.cells), 'lib_sel': self.lib_sel, 'dialog': self._dlg is not None,
                'sheet': self.sheet_rev.get_reveal_child(), 'toast': getattr(self, 'last_toast', None),
                'play_label': self.play_btn.get_label(), 'swing_word': self.swing_word.get_label(),
                'xruns': self.io.xruns if self.io else None, 'callbacks': self.io.callbacks if self.io else None,
                'latency_ms': self.io.latency_s * 1000 if self.io else None,
                'last_export': getattr(self, 'last_export', None), 'audio_err': self.audio_err}

    def ctl_shot(self, path='/tmp/l5s.png'):
        """Render the window to PNG offscreen (works with the screen off / locked).

        PyGObject 3.40 can't wrap GskRenderNode, so the whole chain runs in C via ctypes.
        """
        import ctypes as C
        gtk = C.CDLL('libgtk-4.so.1')
        get = C.pythonapi.PyCapsule_GetPointer
        get.restype, get.argtypes = C.c_void_p, [C.py_object, C.c_char_p]
        win = get(self.win.__gpointer__, None)
        w, h = self.win.get_width(), self.win.get_height()

        class Rect(C.Structure):
            _fields_ = [('x', C.c_float), ('y', C.c_float), ('w', C.c_float), ('h', C.c_float)]
        for fn, res, args in (('gtk_snapshot_new', C.c_void_p, []),
                              ('gtk_widget_paintable_new', C.c_void_p, [C.c_void_p]),
                              ('gdk_paintable_snapshot', None, [C.c_void_p, C.c_void_p, C.c_double, C.c_double]),
                              ('gtk_snapshot_free_to_node', C.c_void_p, [C.c_void_p]),
                              ('gtk_native_get_renderer', C.c_void_p, [C.c_void_p]),
                              ('gsk_renderer_render_texture', C.c_void_p, [C.c_void_p, C.c_void_p, C.POINTER(Rect)]),
                              ('gdk_texture_save_to_png', C.c_bool, [C.c_void_p, C.c_char_p]),
                              ('gsk_render_node_unref', None, [C.c_void_p]),
                              ('g_object_unref', None, [C.c_void_p])):
            f = getattr(gtk, fn)
            f.restype, f.argtypes = res, args
        snap = gtk.gtk_snapshot_new()
        paint = gtk.gtk_widget_paintable_new(win)
        gtk.gdk_paintable_snapshot(paint, snap, w, h)
        node = gtk.gtk_snapshot_free_to_node(snap)
        if not node:
            gtk.g_object_unref(paint)
            self.win.queue_draw()
            return {'ok': False, 'retry': True}
        r = Rect(0, 0, w, h)
        tex = gtk.gsk_renderer_render_texture(gtk.gtk_native_get_renderer(win), node, C.byref(r))
        okk = gtk.gdk_texture_save_to_png(tex, path.encode())
        gtk.gsk_render_node_unref(node)
        gtk.g_object_unref(tex)
        gtk.g_object_unref(paint)
        return {'path': path, 'w': w, 'h': h, 'ok': bool(okk)}

    def ctl_call(self, name, args=()):
        r = getattr(self, name)(*args)
        return r if isinstance(r, (dict, list, str, int, float, type(None))) else str(r)

    def ctl_set(self, widget, value):
        getattr(self, widget).set_value(value)
        return True

    def ctl_dialog(self, response):
        if not self._dlg:
            return False
        self._dlg.response(response)
        return True

    def ctl_hits(self, clear=False):
        h = list(self.engine.hit_log)
        if clear:
            self.engine.hit_log.clear()
        return h

    def ctl_swipe_open(self, index):
        allx = sorted(self.sounds.values(), key=lambda s: -s['created'])
        front = self.lib_rows[allx[index]['id']]
        front.set_margin_end(96)
        front.get_parent().get_child().set_opacity(1)
        self.open_row = front
        return allx[index]['name']


def main():
    app = SamplerApp()
    return app.run(None)
