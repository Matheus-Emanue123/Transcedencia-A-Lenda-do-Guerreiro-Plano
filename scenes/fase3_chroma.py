"""
FASE III - O Véu Esmeralda  (Chroma Key)

O Ilusionista escondeu o caminho atrás de um véu verde. Sir Lineu escolhe a
cor-chave (conta-gotas) e a tolerância: pixels próximos da chave no espaço
RGB são trocados pelo "fundo real". Tolerância baixa deixa restos do véu;
tolerância alta apaga também a floresta verdadeira (árvores e grama).
"""
import math
import random
import numpy as np
import pygame

from engine.core import Phase, W, H
from engine.assets import text
from engine.ui import C, Button, Slider, panel
from engine import cg, audio, scenery

WORLD_H = 430
OY = 40
PANEL = pygame.Rect(16, 478, W - 32, 222)
VEIL_COL = np.array([12, 246, 24])


class Fase3(Phase):
    index = 2
    music = 'fase3'
    ambience = ['amb_forest']
    title = 'Fase III - O Véu Esmeralda'
    subtitle = 'Chroma key'
    concept_title = 'Chroma key: recorte por cor-chave'
    concept = (
        "Chroma key (o 'fundo verde' do cinema) substitui todos os pixels de uma cor-chave por outra imagem.\n\n"
        "Para cada pixel P = (R,G,B) da imagem da frente, medimos a distância euclidiana até a cor-chave K:\n"
        "   d = √( (R-Kr)² + (G-Kg)² + (B-Kb)² )\n"
        "Se d < tolerância  ->  o pixel vira o pixel do fundo (máscara = 1)\n"
        "Senão              ->  o pixel da frente é mantido.\n\n"
        "Por que verde? Porque é a cor mais distante dos tons de pele humana e os sensores das câmeras são "
        "mais sensíveis ao verde (padrão de Bayer).\n\n"
        "O véu do Ilusionista não é perfeitamente uniforme (tem ruído), então a tolerância precisa ser grande o "
        "bastante para cobrir essa variação - mas pequena o bastante para NÃO apagar o que é verde de verdade "
        "(árvores e grama). Use o conta-gotas no véu (ele faz a média de uma vizinhança 5x5) e ajuste a tolerância.\n"
        "Meta: remover ≥ 97% do véu e apagar ≤ 3% do mundo real."
    )
    intro = [
        ('Ilusionista', 'illusionist', 'Ha-ha! Ninguém passa pela Floresta Esmeralda! Meu véu verde '
                                       'esconde o caminho... e você nem sabe o que há atrás dele!'),
        ('Volumar', 'wizard', 'Truque antigo. É um fundo de cor-chave, Lineu. Use o conta-gotas para clicar '
                              'no véu e escolher a cor-chave; depois ajuste a tolerância.'),
        ('Volumar', 'wizard', 'Mas não exagere! As árvores e a grama também são verdes. Apagar a floresta '
                              'verdadeira seria um desastre.'),
    ]
    outro = [
        ('Ilusionista', 'illusionist', 'Impossível! Você separou o falso do verdadeiro pixel a pixel!'),
        ('Sir Lineu', 'knight', 'Uma imagem é só uma matriz de cores. Basta saber medir distâncias.'),
        ('Volumar', 'wizard', 'O caminho leva à Fortaleza das Matrizes. Lá, as formas obedecem a '
                              'transformações. Você vai precisar mover, girar e escalar o próprio mundo.'),
    ]

    def setup(self):
        rnd = random.Random(7)
        self.bg = pygame.Surface((W, WORLD_H))
        self.build_real(self.bg, rnd)
        bg_arr = pygame.surfarray.array3d(self.bg)
        # véu: região ondulada com ruído
        xs, ys = np.meshgrid(np.arange(W), np.arange(WORLD_H), indexing='ij')
        edge = 640 + 40 * np.sin(ys / 37.0) + 18 * np.sin(ys / 11.0)
        top = 60 + 20 * np.sin(xs / 50.0)
        veil = (xs > edge) & (ys > top) & (xs < 1240 + 20 * np.sin(ys / 23.0))
        rng = np.random.default_rng(3)
        noise = rng.integers(-18, 19, size=(W, WORLD_H, 3))
        shade = (np.sin(xs / 60.0 + ys / 45.0) * 8)[..., None]
        veil_px = np.clip(VEIL_COL + noise + shade, 0, 255)
        fg_arr = np.where(veil[..., None], veil_px, bg_arr).astype(np.uint8)
        # o ilusionista desenha uma "parede falsa" sobre o véu? Não: o véu é a ilusão.
        self.bg_arr = bg_arr
        self.fg_arr = fg_arr
        self.veil = veil
        r, g, b = bg_arr[..., 0].astype(int), bg_arr[..., 1].astype(int), bg_arr[..., 2].astype(int)
        self.greenish = (~veil) & (g > r + 20) & (g > b + 20)
        self.fg = pygame.Surface((W, WORLD_H))
        pygame.surfarray.blit_array(self.fg, fg_arr)
        self.out = self.fg.copy()
        self.key = None
        self.tol = Slider((PANEL.x + 30, PANEL.y + 110, 380, 18), 'Tolerância (distância RGB)', 0, 200, 0, 2,
                          '{:.0f}', C['gold'], on_change=lambda v: self.recompute())
        self.cast = Button((PANEL.x + 30, PANEL.bottom - 52, 260, 40), 'Lançar contra-feitiço', self.check, 20,
                           hotkey=pygame.K_RETURN)
        self.stats = (0.0, 0.0)
        self.done_t = 0
        self.kx = 90.0
        self.hud_hint = 'Clique no cenário para escolher a cor-chave (conta-gotas)'

    def build_real(self, s, rnd):
        scenery.gradient(s, (0, 0, W, WORLD_H), (90, 150, 220), (170, 210, 240))
        scenery.hills(s, self.assets, 120, scale=4, height=200)
        scenery.ground(s, self.assets, WORLD_H - 144, rows=3, rnd=rnd)
        # caminho de pedra escondido + porta rúnica
        for x in range(0, W, 48):
            s.blit(self.assets.sprite('cobble' if x > 640 else 'path', 3), (x, WORLD_H - 96))
        wall_x = 1010
        for j in range(5):
            for i in range(4):
                s.blit(self.assets.sprite('wall', 3), (wall_x + i * 48, WORLD_H - 96 - (j + 1) * 48))
        s.blit(self.assets.sprite('door', 3), (wall_x + 48, WORLD_H - 144))
        s.blit(self.assets.sprite('door', 3), (wall_x + 96, WORLD_H - 144))
        s.blit(self.assets.sprite('torch_wall', 3), (wall_x, WORLD_H - 192))
        s.blit(self.assets.sprite('shield_crest', 3), (wall_x + 72, WORLD_H - 290))
        s.blit(self.assets.sprite('illusionist', 4), (860, WORLD_H - 160))
        s.blit(self.assets.sprite('chest', 3), (780, WORLD_H - 140))
        for i, ch in enumerate('MATRIZES'):
            pygame.draw.circle(s, (240, 200, 90), (735 + i * 34, 150), 13)
            f = pygame.font.Font(None, 26)
            s.blit(f.render(ch, True, (60, 30, 10)), (729 + i * 34, 141))
        for x, k in [(60, 'tree'), (150, 'tree_pine'), (260, 'tree'), (330, 'bush'), (420, 'tree_pine'), (500, 'tree'),
                     (590, 'tree_pine'), (700, 'tree'), (960, 'tree_pine'), (1240, 'tree')]:
            scenery.tree(s, self.assets, x, WORLD_H - 140, k, scale=4)

    def recompute(self):
        if self.key is None:
            return
        out, mask = cg.chroma_key(self.fg_arr, self.bg_arr, self.key, self.tol.value)
        pygame.surfarray.blit_array(self.out, out)
        veil_removed = (mask & self.veil).sum() / max(1, self.veil.sum())
        real_removed = (mask & self.greenish).sum() / max(1, self.greenish.sum())
        self.mask = mask
        self.stats = (veil_removed, real_removed)

    def check(self):
        if self.key is None:
            self.toast('Primeiro escolha a cor-chave com o conta-gotas!', C['red'])
            return
        v, r = self.stats
        if v >= 0.97 and r <= 0.03:
            self.toast('O véu se desfez!', C['green'])
            self.done_t = 0.01
            audio.sfx('spell')
            audio.sfx('whoosh')
            audio.sfx('ui_glass', 0.7)
            self.hud_hint = ''
        elif v < 0.97 and r > 0.03:
            self.toast('Cor-chave errada: isso não é a cor do véu!', C['red'])
        elif v < 0.97:
            self.toast(f'Ainda restam {100 * (1 - v):.1f}% do véu. Aumente a tolerância.', C['red'])
        else:
            self.toast(f'Você apagou {100 * r:.1f}% da floresta real! Diminua a tolerância.', C['red'])

    def on_event(self, e):
        if self.done_t:
            return
        if self.tol.handle(e):
            return
        if self.cast.handle(e):
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and OY <= e.pos[1] < OY + WORLD_H:
            x, y = e.pos[0], e.pos[1] - OY
            x0, x1 = max(0, x - 2), min(W, x + 3)
            y0, y1 = max(0, y - 2), min(WORLD_H, y + 3)
            patch = self.fg_arr[x0:x1, y0:y1].reshape(-1, 3)
            self.key = tuple(int(v) for v in patch.mean(axis=0))
            audio.sfx('ui_drop')
            self.recompute()
            self.hud_hint = 'Ajuste a tolerância e lance o contra-feitiço (ENTER)'

    def on_update(self, dt, paused):
        if paused:
            return
        if self.done_t:
            self.done_t += dt
            if self.done_t > 1.0:
                if int((self.kx + 200 * dt) / 38) != int(self.kx / 38):
                    audio.sfx('step_grass')
                self.kx += 200 * dt
                if self.kx > 1080:
                    self.kx = 1080
                    if self.done_t > 1.0:
                        self.complete()

    def on_draw(self, surf):
        surf.fill(C['bg'])
        if self.done_t:
            a = min(1, self.done_t)
            surf.blit(self.out, (0, OY))
            b = self.bg.copy()
            b.set_alpha(int(255 * a))
            surf.blit(b, (0, OY))
        else:
            surf.blit(self.out if self.key else self.fg, (0, OY))
        k = self.assets.sprite('knight', 4)
        surf.blit(k, k.get_rect(midbottom=(self.kx, OY + WORLD_H - 90)))
        m = pygame.mouse.get_pos()
        if not self.done_t and OY <= m[1] < OY + WORLD_H and not (self.dialog and self.dialog.active):
            pygame.draw.circle(surf, (255, 255, 255), m, 10, 2)
            pygame.draw.line(surf, (255, 255, 255), (m[0] - 16, m[1]), (m[0] - 6, m[1]), 2)
            pygame.draw.line(surf, (255, 255, 255), (m[0] + 6, m[1]), (m[0] + 16, m[1]), 2)
            c = surf.get_at(m)[:3]
            pygame.draw.rect(surf, c, (m[0] + 16, m[1] + 16, 28, 28))
            pygame.draw.rect(surf, (255, 255, 255), (m[0] + 16, m[1] + 16, 28, 28), 2)
        self.draw_panel(surf)

    def draw_panel(self, surf):
        panel(surf, PANEL, alpha=240)
        text(surf, 'Contra-feitiço de Chroma Key', (PANEL.x + 30, PANEL.y + 12), 24, C['gold'])
        text(surf, 'Cor-chave K:', (PANEL.x + 30, PANEL.y + 50), 19)
        if self.key:
            pygame.draw.rect(surf, self.key, (PANEL.x + 150, PANEL.y + 46, 40, 30), border_radius=4)
            pygame.draw.rect(surf, C['border'], (PANEL.x + 150, PANEL.y + 46, 40, 30), 2, border_radius=4)
            text(surf, str(self.key), (PANEL.x + 200, PANEL.y + 50), 18, C['text'], kind='mono')
        else:
            text(surf, '(clique no cenário)', (PANEL.x + 150, PANEL.y + 50), 18, C['dim'])
        self.tol.draw(surf)
        self.cast.draw(surf)
        fx = PANEL.x + 470
        text(surf, 'Para cada pixel P:', (fx, PANEL.y + 16), 19, C['gold'])
        text(surf, 'd = √((R-Kr)² + (G-Kg)² + (B-Kb)²)', (fx, PANEL.y + 46), 18, C['text'], kind='mono')
        text(surf, f'd < {self.tol.value:.0f}  ->  pixel do FUNDO real', (fx, PANEL.y + 74), 18, C['text'], kind='mono')
        text(surf, f'd ≥ {self.tol.value:.0f}  ->  mantém a FRENTE', (fx, PANEL.y + 100), 18, C['text'], kind='mono')
        v, r = self.stats
        bx = fx
        text(surf, 'Véu removido', (bx, PANEL.y + 136), 18)
        self.bar(surf, (bx + 170, PANEL.y + 140, 260, 18), v, C['green'] if v >= 0.97 else C['gold'])
        text(surf, f'{100 * v:5.1f}%  (meta ≥ 97%)', (bx + 440, PANEL.y + 136), 17, C['text'], kind='mono')
        text(surf, 'Floresta apagada', (bx, PANEL.y + 168), 18)
        self.bar(surf, (bx + 170, PANEL.y + 172, 260, 18), r, C['red'] if r > 0.03 else C['green'])
        text(surf, f'{100 * r:5.1f}%  (meta ≤ 3%)', (bx + 440, PANEL.y + 168), 17, C['text'], kind='mono')

    def bar(self, surf, rect, v, col):
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, (20, 16, 20), r, border_radius=4)
        f = r.copy()
        f.w = int(r.w * max(0, min(1, v)))
        pygame.draw.rect(surf, col, f, border_radius=4)
        pygame.draw.rect(surf, C['border_dark'], r, 2, border_radius=4)
