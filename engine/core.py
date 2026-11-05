"""Núcleo do jogo: game loop com delta time, gerenciador de cenas e base das fases."""
import json
import os
import pygame

from .assets import Assets, ROOT, text, text_block, font
from .ui import C, Dialog, panel
from . import audio

W, H = 1280, 720
FPS = 60
SAVE = os.path.join(ROOT, 'save.json')


class Scene:
    def __init__(self, game):
        self.game = game
        self.assets = game.assets

    def handle(self, e):
        pass

    def update(self, dt):
        pass

    def draw(self, surf):
        pass


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption('Transcendência - A Lenda do Cavaleiro Plano')
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.assets = Assets()
        self.audio = audio.get()
        self.scene = None
        self._next = None
        self._fade = 0.0
        self._fade_dir = 0
        self.running = True
        self.progress = self._load()
        self.show_fps = False
        self.driver = None          # piloto automático (modo demonstração)

    # ------------------------------------------------------------- progresso
    def _load(self):
        try:
            with open(SAVE, 'r', encoding='utf8') as f:
                return json.load(f)
        except Exception:
            return {'done': []}

    def mark_done(self, idx):
        if idx not in self.progress['done']:
            self.progress['done'].append(idx)
        try:
            with open(SAVE, 'w', encoding='utf8') as f:
                json.dump(self.progress, f)
        except Exception:
            pass

    # ------------------------------------------------------------------ cenas
    def goto(self, factory, instant=False):
        """factory: callable(game) -> Scene. Faz fade-out / fade-in."""
        if instant or self.scene is None:
            self.scene = factory(self)
            self._fade, self._fade_dir = (1.0, -1) if self.scene else (0, 0)
            return
        self._next = factory
        self._fade_dir = 1

    def goto_phase(self, idx):
        from scenes import PHASES, ending
        if idx >= len(PHASES):
            self.goto(lambda g: ending.Ending(g))
        else:
            self.goto(lambda g: PHASES[idx](g))

    def goto_menu(self):
        from scenes import menu
        self.goto(lambda g: menu.Menu(g))

    def run(self, first):
        self.goto(first, instant=True)
        while self.running:
            # Delta time: movimento independente do FPS (aula de dispositivos/FPS)
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                    self.show_fps = not self.show_fps
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F2:
                    self.audio.toggle_mute()
                elif self.driver and not self.driver.accept_real(e):
                    continue
                elif self._fade_dir == 0:
                    self.scene.handle(e)
            if self.driver and self._fade_dir == 0:
                self.driver.update(dt)
            if self._fade_dir == 0:
                self.scene.update(dt)
            else:
                self._fade += self._fade_dir * dt * 3.0
                if self._fade_dir > 0 and self._fade >= 1:
                    self._fade = 1
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                    self.scene = self._next(self)
                    self._next = None
                    self._fade_dir = -1
                elif self._fade_dir < 0 and self._fade <= 0:
                    self._fade = 0
                    self._fade_dir = 0
            self.scene.draw(self.screen)
            if self._fade > 0:
                s = pygame.Surface((W, H))
                s.fill((0, 0, 0))
                s.set_alpha(int(255 * self._fade))
                self.screen.blit(s, (0, 0))
            if self.driver:
                self.driver.draw(self.screen)
            if self.show_fps:
                text(self.screen, f'{self.clock.get_fps():.0f} FPS', (W - 10, H - 26), 16, C['green'], kind='mono', right=True)
            pygame.display.flip()
        pygame.quit()


class Phase(Scene):
    """Base de todas as fases: diálogo de introdução, jogo, painel de conceito
    (tecla H), mensagens rápidas e diálogo de conclusão."""
    index = 0
    title = 'Fase'
    subtitle = ''
    concept_title = ''
    concept = ''
    intro = []
    outro = []
    hud_hint = ''
    music = None
    ambience = []
    sound_style = 'medieval'

    def __init__(self, game):
        super().__init__(game)
        a = audio.get()
        a.style = self.sound_style
        a.stop_loop()
        if self.music:
            audio.music(self.music)
        audio.ambience(self.ambience)
        audio.sfx('gong')
        self.dialog = None
        self.show_help = False
        self.toast_msg = None
        self.toast_t = 0
        self.toast_col = C['text']
        self.completed = False
        self.t = 0.0
        self.title_card = 2.2
        self.setup()
        if self.intro:
            self.say(self.intro)

    def setup(self):
        pass

    # ---------------------------------------------------------------- utils
    def say(self, lines, then=None):
        self.dialog = Dialog(self.assets, lines, then)

    def toast(self, msg, color=None, t=2.6):
        self.toast_msg = msg
        self.toast_t = t
        self.toast_col = color or C['text']
        if color in (C['green'], C['gold']):
            audio.get().ok_jingle()
        elif color == C['red']:
            audio.get().fail_jingle()
            audio.sfx('ui_error')

    def complete(self):
        if self.completed:
            return
        self.completed = True
        audio.get().stop_loop()
        audio.get().win_jingle()
        self.game.mark_done(self.index)
        nxt = self.index + 1
        if self.outro:
            self.say(self.outro, lambda: self.game.goto_phase(nxt))
        else:
            self.game.goto_phase(nxt)

    # ------------------------------------------------------------- eventos
    def handle(self, e):
        if self.dialog and self.dialog.active:
            self.dialog.handle(e)
            return
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_h or e.key == pygame.K_F1:
                self.show_help = not self.show_help
                audio.sfx('book_open' if self.show_help else 'book_close')
                return
            if e.key == pygame.K_ESCAPE:
                if self.show_help:
                    self.show_help = False
                    audio.sfx('book_close')
                else:
                    audio.sfx('ui_back')
                    self.game.goto_menu()
                return
            if e.key == pygame.K_F5:
                audio.sfx('ui_back')
                self.game.goto_phase(self.index)
                return
            if e.key == pygame.K_F9:          # atalho para apresentação
                self.complete()
                return
        if self.show_help:
            if e.type == pygame.MOUSEBUTTONDOWN:
                self.show_help = False
                audio.sfx('book_close')
            return
        if not self.completed:
            self.on_event(e)

    def update(self, dt):
        self.t += dt
        if self.toast_t > 0:
            self.toast_t -= dt
        if self.title_card > 0 and not (self.dialog and self.dialog.active):
            self.title_card -= dt
        if self.dialog and self.dialog.active:
            self.dialog.update(dt)
            self.on_update(dt, paused=True)
            return
        if not self.show_help:
            self.on_update(dt, paused=False)

    def draw(self, surf):
        self.on_draw(surf)
        # barra superior
        bar = pygame.Surface((W, 40), pygame.SRCALPHA)
        bar.fill((10, 8, 16, 210))
        surf.blit(bar, (0, 0))
        pygame.draw.line(surf, C['border_dark'], (0, 40), (W, 40), 2)
        text(surf, f'{self.title}', (14, 7), 22, C['gold'])
        text(surf, self.subtitle, (14 + font(22).size(self.title)[0] + 18, 10), 18, C['dim'])
        text(surf, 'H: conceito   F2: som' + (' (mudo)' if self.game.audio.muted else '') + '   F5: reiniciar   ESC: menu', (W - 14, 11), 16, C['dim'], right=True)
        if self.hud_hint and not (self.dialog and self.dialog.active):
            f = font(17)
            hw = f.size(self.hud_hint)[0] + 32
            pill = pygame.Surface((hw, 28), pygame.SRCALPHA)
            pygame.draw.rect(pill, (10, 8, 16, 200), pill.get_rect(), border_radius=14)
            surf.blit(pill, (W // 2 - hw // 2, H - 36))
            text(surf, self.hud_hint, (W // 2, H - 22), 17, C['parch'], center=True)
        if self.toast_t > 0 and self.toast_msg:
            f = font(26)
            w = f.size(self.toast_msg)[0] + 50
            r = pygame.Rect(0, 0, w, 52)
            r.center = (W // 2, 90)
            panel(surf, r, alpha=235)
            text(surf, self.toast_msg, r.center, 26, self.toast_col, center=True)
        if self.title_card > 0 and not (self.dialog and self.dialog.active) and not self.completed:
            a = min(1, self.title_card)
            s = pygame.Surface((W, 120), pygame.SRCALPHA)
            s.fill((0, 0, 0, int(170 * a)))
            surf.blit(s, (0, H // 2 - 60))
            text(surf, self.title, (W // 2, H // 2 - 28), 44, C['gold'], center=True)
            text(surf, self.concept_title, (W // 2, H // 2 + 24), 24, C['parch'], center=True)
        if self.show_help:
            self.draw_help(surf)
        if self.dialog and self.dialog.active:
            self.dialog.draw(surf)

    def draw_help(self, surf):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        surf.blit(s, (0, 0))
        r = pygame.Rect(140, 70, W - 280, H - 140)
        panel(surf, r, alpha=250)
        text(surf, 'Pergaminho do Conhecimento', (r.centerx, r.y + 30), 30, C['gold'], center=True)
        text(surf, self.concept_title, (r.centerx, r.y + 66), 22, C['parch'], center=True)
        text_block(surf, self.concept, (r.x + 40, r.y + 104, r.w - 80, r.h - 140), 19, C['text'], kind='serif')
        text(surf, 'H ou clique para fechar', (r.centerx, r.bottom - 26), 16, C['dim'], center=True)

    # ----------------------------------------------------- para sobrescrever
    def on_event(self, e):
        pass

    def on_update(self, dt, paused):
        pass

    def on_draw(self, surf):
        surf.fill(C['bg'])
