"""
audio.py - Trilha sonora, efeitos sonoros e ambientes.

Músicas: arquivos CC0 do OpenGameArt em assets/music (a trilha evolui junto
com o mundo: chiptune 8-bit -> medieval acústico -> orquestra/coral no 3D).
Efeitos: ~100 sons CC0 (Kenney e OpenGameArt) em assets/sfx, recortados e
normalizados. Variações (nome_1, nome_2, ...) são sorteadas para não soar
repetitivo.
Ambientes: até 2 camadas em loop por cena (pássaros, rio, vento, fogo...).
Alguns bipes 8-bit (pixels da Fase I, fanfarra final) são sintetizados com
numpy: onda quadrada/triangular/ruído + envelope exponencial.
"""
import os
import random
import re
import time

import numpy as np
import pygame

from .assets import ASSETS

SR = 44100
MUSIC_DIR = os.path.join(ASSETS, 'music')
SFX_DIR = os.path.join(ASSETS, 'sfx')
MUSIC_VOL = 0.40
SFX_VOL = 0.70
AMB_VOL = 0.55

# volume relativo por som (os demais usam 1.0)
VOL = {
    'ui_hover': 0.35, 'ui_type': 0.30, 'ui_scroll': 0.45, 'page': 0.55, 'pixel': 0.6, 'pixel2': 0.6,
    'step_grass': 0.45, 'step_stone': 0.40, 'gong': 0.55, 'wings': 0.9, 'hum_rotate': 0.5,
}
# intervalo mínimo entre repetições do mesmo som (evita "metralhadora" de cliques)
THROTTLE = {'ui_scroll': 0.045, 'ui_type': 0.035, 'ui_hover': 0.05, 'pixel': 0.02, 'pixel2': 0.04,
            'ui_error': 0.15, 'step_grass': 0.12, 'step_stone': 0.12}


# --------------------------------------------------------------------------
# Síntese 8-bit
# --------------------------------------------------------------------------
def _wave(kind, freq, t):
    ph = 2 * np.pi * np.cumsum(freq) / SR
    if kind == 'square':
        return np.sign(np.sin(ph)) * 0.6
    if kind == 'tri':
        return 2 / np.pi * np.arcsin(np.sin(ph))
    if kind == 'saw':
        return 2 * ((ph / (2 * np.pi)) % 1) - 1
    if kind == 'noise':
        return np.random.default_rng(1).uniform(-1, 1, len(t))
    return np.sin(ph)


def tone(freq, dur, kind='square', vol=0.5, decay=6.0, sweep=1.0, attack=0.005):
    """Uma nota: frequência inicial com varredura multiplicativa até freq*sweep."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = freq * np.power(sweep, t / max(dur, 1e-6))
    x = _wave(kind, f, t)
    env = np.exp(-decay * t) * np.clip(t / attack, 0, 1)
    env[-min(200, n):] *= np.linspace(1, 0, min(200, n))
    return x * env * vol


def seq(*parts):
    return np.concatenate(parts)


def note(n):
    """Número MIDI -> frequência (A4 = 69 = 440 Hz)."""
    return 440.0 * 2 ** ((n - 69) / 12)


def build_synth():
    return {
        'pixel': tone(660, 0.03, 'square', 0.12, 60),
        'pixel2': tone(990, 0.03, 'square', 0.12, 60),
        'victory': seq(*[tone(note(n), 0.14, 'square', 0.3, 6) for n in (67, 72, 76, 79, 76, 79)],
                       tone(note(84), 0.8, 'square', 0.3, 3)),
    }


# --------------------------------------------------------------------------
class Audio:
    MUSIC = {
        'menu': 'menu.mp3', 'fase1': 'fase1.mp3', 'fase2': 'fase2.mp3', 'fase3': 'fase3.mp3',
        'fase4': 'fase4.mp3', 'fase6': 'fase6.mp3', 'fase7': 'fase7.ogg', 'fase9': 'fase9.mp3',
        'boss': 'boss.wav', 'ending': 'ending.mp3',
    }

    def __init__(self):
        self.ok = False
        self.muted = False
        self.current = None
        self.style = 'medieval'          # estilo dos jingles: '8bit' (Fases I-II) ou 'medieval'
        self.groups = {}
        self.last = {}
        self.last_pick = {}
        self.amb_names = []
        self.loop_name = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 2, 512)
            pygame.mixer.set_num_channels(32)
            pygame.mixer.set_reserved(3)          # 0, 1 = ambiente   2 = loop contínuo
            self.ok = True
        except Exception:
            return
        self.amb_ch = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
        self.loop_ch = pygame.mixer.Channel(2)
        self._load_files()
        self._load_synth()

    def _add(self, name, snd):
        base = re.sub(r'_\d+$', '', name)
        self.groups.setdefault(base, []).append(snd)
        if base != name:
            self.groups.setdefault(name, []).append(snd)

    def _load_files(self):
        if not os.path.isdir(SFX_DIR):
            return
        for f in sorted(os.listdir(SFX_DIR)):
            name, ext = os.path.splitext(f)
            if ext.lower() in ('.wav', '.ogg', '.mp3'):
                try:
                    self._add(name, pygame.mixer.Sound(os.path.join(SFX_DIR, f)))
                except Exception:
                    pass

    def _load_synth(self):
        _, _, ch = pygame.mixer.get_init()
        for name, x in build_synth().items():
            a = (np.clip(x, -1, 1) * 32767).astype(np.int16)
            if ch == 2:
                a = np.ascontiguousarray(np.column_stack([a, a]))
            try:
                self._add(name, pygame.sndarray.make_sound(a))
            except Exception:
                pass

    # ------------------------------------------------------------------ música
    def music(self, name):
        if not self.ok or name == self.current:
            return
        self.current = name
        try:
            pygame.mixer.music.fadeout(400)
            pygame.mixer.music.load(os.path.join(MUSIC_DIR, self.MUSIC.get(name, '')))
            pygame.mixer.music.set_volume(0 if self.muted else MUSIC_VOL)
            pygame.mixer.music.play(-1, fade_ms=1200)
        except Exception:
            pass

    # ----------------------------------------------------------------- efeitos
    def play(self, name, vol=1.0):
        if not self.ok or self.muted:
            return None
        grp = self.groups.get(name)
        if not grp:
            return None
        now = time.perf_counter()
        if now - self.last.get(name, -9.0) < THROTTLE.get(name, 0.0):
            return None
        self.last[name] = now
        idx = random.randrange(len(grp))
        if len(grp) > 1 and idx == self.last_pick.get(name):
            idx = (idx + 1) % len(grp)
        self.last_pick[name] = idx
        snd = grp[idx]
        base = re.sub(r'_\d+$', '', name)
        snd.set_volume(max(0.0, min(1.0, SFX_VOL * VOL.get(base, 1.0) * vol)))
        return snd.play()

    def ok_jingle(self):
        self.play('jingle_ok8' if self.style == '8bit' else 'jingle_ok')

    def fail_jingle(self):
        self.play('jingle_fail8' if self.style == '8bit' else 'jingle_fail')

    def win_jingle(self):
        self.play('jingle_win8' if self.style == '8bit' else 'jingle_win')

    # ---------------------------------------------------------------- ambiente
    def ambience(self, names):
        """Define até 2 camadas de som ambiente em loop (com fade)."""
        names = list(names or [])[:2]
        if not self.ok or names == self.amb_names:
            return
        self.amb_names = names
        for ch in self.amb_ch:
            ch.fadeout(800)
        for i, n in enumerate(names):
            grp = self.groups.get(n)
            if grp:
                self.amb_ch[i].set_volume(0 if self.muted else AMB_VOL)
                self.amb_ch[i].play(grp[0], loops=-1, fade_ms=1500)

    def loop(self, name, on, vol=1.0):
        """Som contínuo enquanto 'on' for verdadeiro (ex.: zumbido ao girar o cristal)."""
        if not self.ok:
            return
        if on and not self.muted and name in self.groups:
            if self.loop_name != name:
                self.loop_ch.play(self.groups[name][0], loops=-1, fade_ms=150)
                self.loop_name = name
            self.loop_ch.set_volume(SFX_VOL * VOL.get(name, 1.0) * vol)
        elif self.loop_name:
            self.loop_ch.fadeout(250)
            self.loop_name = None

    def stop_loop(self):
        if self.ok:
            self.loop_ch.stop()
            self.loop_name = None

    def toggle_mute(self):
        self.muted = not self.muted
        if self.ok:
            pygame.mixer.music.set_volume(0 if self.muted else MUSIC_VOL)
            for ch in self.amb_ch:
                ch.set_volume(0 if self.muted else AMB_VOL)
            if self.muted:
                self.stop_loop()
        return self.muted


_instance = None


def get():
    global _instance
    if _instance is None:
        _instance = Audio()
    return _instance


def sfx(name, vol=1.0):
    return get().play(name, vol)


def music(name):
    get().music(name)


def ambience(names):
    get().ambience(names)
