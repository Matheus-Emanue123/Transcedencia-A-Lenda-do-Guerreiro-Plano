"""
FASE IV - A Fortaleza das Matrizes  (Transformações 2D em coordenadas homogêneas)

Cada portão tem uma fechadura com a silhueta da Chave Dimensional numa nova
posição/orientação/tamanho. O jogador compõe matrizes 3x3 (translação, escala,
rotação, reflexão, cisalhamento) até a chave encaixar na silhueta.
"""
import math
import numpy as np
import pygame

from engine.core import Phase, W, H
from engine.assets import text, text_block
from engine.ui import C, Button, Slider, panel, matrix_view, dashed_poly
from engine import cg, audio

AREA = pygame.Rect(16, 50, 790, 650)
ORIGIN = (AREA.centerx, AREA.centery)
SCALE = 34
PX = 822

KEY = [(-2.0, 0.6), (-0.6, 0.6), (-0.6, 0.2), (1.6, 0.2), (1.6, -0.3), (1.2, -0.3), (1.2, -0.7),
       (0.9, -0.7), (0.9, -0.3), (0.5, -0.3), (0.5, -0.55), (0.2, -0.55), (0.2, -0.3), (-0.6, -0.3),
       (-0.6, -0.6), (-2.0, -0.6)]

LOCKS = [
    {'name': 'Portão do Leste', 'start': np.eye(3), 'target': cg.T2(4, 2.5),
     'desc': 'A fechadura está deslocada. Uma TRANSLAÇÃO basta: x\' = x + tx, y\' = y + ty.'},
    {'name': 'Portão das Torres', 'start': np.eye(3), 'target': cg.T2(-4, 1.5) @ cg.R2(90),
     'desc': 'A chave precisa ficar de pé e ir para a esquerda. ROTAÇÃO (em torno da origem) e TRANSLAÇÃO.'},
    {'name': 'Portão do Gigante', 'start': cg.T2(4, -3), 'target': cg.T2(4, -3) @ cg.S2(1.75, 1.75),
     'desc': 'Escale a chave 1.75x SEM tirá-la do lugar. A escala é feita em relação à origem... '
             'leve a chave até a origem, escale e devolva!'},
    {'name': 'Portão do Espelho', 'start': np.eye(3), 'target': cg.Sh2(0.5, 0) @ cg.Ref2('y'),
     'desc': 'Uma fechadura espelhada e inclinada. REFLEXÃO e CISALHAMENTO - a ORDEM importa: A·B ≠ B·A.'},
    {'name': 'Portão do Rei', 'start': cg.T2(-4, 2), 'target': cg.T2(-4, 2) @ cg.R2(-135) @ cg.S2(0.75, 0.75),
     'desc': 'Gire -135° e reduza para 0.75x em torno do PRÓPRIO centro da chave (em (-4, 2)). '
             'Composição: T(c) · R · S · T(-c).'},
]

OPS = ['Translação', 'Escala', 'Rotação', 'Reflexão X', 'Reflexão Y', 'Cisalhamento']


def to_screen(p):
    return (ORIGIN[0] + p[0] * SCALE, ORIGIN[1] - p[1] * SCALE)


class Fase4(Phase):
    index = 3
    music = 'fase4'
    ambience = ['amb_castle']
    title = 'Fase IV - A Fortaleza das Matrizes'
    subtitle = 'Transformações geométricas'
    concept_title = 'Transformações 2D em Coordenadas Homogêneas'
    concept = (
        "Em coordenadas homogêneas o ponto (x, y) vira (x, y, 1). Assim TODAS as transformações - inclusive a "
        "translação, que antes era uma soma - viram multiplicações por matrizes 3x3:\n\n"
        "  Translação T(tx,ty) = [1 0 tx; 0 1 ty; 0 0 1]        Escala S(sx,sy) = [sx 0 0; 0 sy 0; 0 0 1]\n"
        "  Rotação R(θ) = [cosθ -senθ 0; senθ cosθ 0; 0 0 1]    Reflexão em Y = [-1 0 0; 0 1 0; 0 0 1]\n"
        "  Cisalhamento Sh(shx,shy) = [1 shx 0; shy 1 0; 0 0 1]\n\n"
        "COMPOSIÇÃO: aplicar A e depois B equivale a M = B · A (a última operação fica à ESQUERDA). "
        "O produto de matrizes não é comutativo - a ordem importa!\n\n"
        "Escala e rotação acontecem em relação à ORIGEM. Para escalar/girar em torno de um ponto c:\n"
        "  M = T(c) · S · T(-c)      (leva c à origem, transforma, devolve)\n\n"
        "No painel: escolha a operação, ajuste os parâmetros (a prévia fantasma mostra o resultado) e clique "
        "em Aplicar. A matriz acumulada M é aplicada a todos os vértices da chave."
    )
    intro = [
        ('Guarda Real', 'knight2', 'Alto lá! A Fortaleza das Matrizes só abre para quem domina as transformações.'),
        ('Volumar', 'wizard', 'Cada portão tem uma fechadura com a forma da Chave Dimensional, mas em outra '
                              'posição, ângulo ou tamanho. Transforme a chave até ela encaixar.'),
        ('Volumar', 'wizard', 'Aqui o mundo segue o plano cartesiano: o eixo Y cresce para CIMA, ao contrário da '
                              'tela. Toda transformação é uma matriz 3x3 em coordenadas homogêneas.'),
    ]
    outro = [
        ('Guarda Real', 'knight2', 'Os cinco portões se abriram... Ninguém fazia isso desde a Era das Grades.'),
        ('Volumar', 'wizard', 'Você compôs matrizes como um verdadeiro geômetra. Translação, escala, rotação, '
                              'reflexão, cisalhamento - todas unificadas pela coordenada homogênea w = 1.'),
        ('Volumar', 'wizard', 'Agora, encontre o Cartógrafo Real. Vorax foi visto no mapa do reino, e só quem '
                              'entende sistemas de coordenadas consegue localizá-lo.'),
    ]

    def setup(self):
        self.li = 0
        self.op = 0
        self.history = []
        self.opening = 0.0
        self.make_buttons()
        self.load_lock()
        self.hud_hint = ''

    def make_buttons(self):
        self.op_buttons = []
        for i, n in enumerate(OPS):
            b = Button((PX + 8 + (i % 3) * 146, 158 + (i // 3) * 42, 140, 36), n, (lambda k=i: self.select_op(k)), 17)
            self.op_buttons.append(b)
        self.apply_b = Button((PX + 8, 640, 140, 42), 'Aplicar', self.apply, 20, hotkey=pygame.K_RETURN, color=(60, 90, 50))
        self.undo_b = Button((PX + 154, 640, 140, 42), 'Desfazer', self.undo, 20, hotkey=pygame.K_BACKSPACE)
        self.reset_b = Button((PX + 300, 640, 140, 42), 'Resetar', self.reset, 20)

    def load_lock(self):
        L = LOCKS[self.li]
        self.M = L['start'].copy()
        self.history = []
        self.target_pts = cg.apply2(L['target'], KEY)
        self.select_op(self.op)

    def select_op(self, k):
        self.op = k
        for i, b in enumerate(self.op_buttons):
            b.selected = i == k
        x = PX + 20
        if k == 0:
            self.params = [Slider((x, 290, 410, 14), 'tx', -8, 8, 0, 0.5, '{:+.1f}'),
                           Slider((x, 340, 410, 14), 'ty', -8, 8, 0, 0.5, '{:+.1f}')]
        elif k == 1:
            self.params = [Slider((x, 290, 410, 14), 'sx', -3, 3, 1, 0.25, '{:+.2f}'),
                           Slider((x, 340, 410, 14), 'sy', -3, 3, 1, 0.25, '{:+.2f}')]
        elif k == 2:
            self.params = [Slider((x, 290, 410, 14), 'Ângulo (graus)', -180, 180, 0, 15, '{:+.0f}°')]
        elif k == 5:
            self.params = [Slider((x, 290, 410, 14), 'shx', -2, 2, 0, 0.25, '{:+.2f}'),
                           Slider((x, 340, 410, 14), 'shy', -2, 2, 0, 0.25, '{:+.2f}')]
        else:
            self.params = []

    def pending(self):
        v = [p.value for p in self.params]
        if self.op == 0:
            return cg.T2(v[0], v[1]), f'T({v[0]:+.1f}, {v[1]:+.1f})'
        if self.op == 1:
            return cg.S2(v[0], v[1]), f'S({v[0]:.2f}, {v[1]:.2f})'
        if self.op == 2:
            return cg.R2(v[0]), f'R({v[0]:+.0f}°)'
        if self.op == 3:
            return cg.Ref2('x'), 'Ref_X'
        if self.op == 4:
            return cg.Ref2('y'), 'Ref_Y'
        return cg.Sh2(v[0], v[1]), f'Sh({v[0]:+.2f}, {v[1]:+.2f})'

    def apply(self):
        if self.opening:
            return
        P, name = self.pending()
        self.history.append((self.M.copy(), name))
        audio.sfx('metal_apply')
        self.M = P @ self.M                     # nova operação à ESQUERDA
        self.select_op(self.op)
        cur = cg.apply2(self.M, KEY)
        err = max(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(cur, self.target_pts))
        if err < 0.12:
            self.opening = 0.01
            audio.sfx('lock')
            audio.sfx('door_open')
            self.toast(f'{LOCKS[self.li]["name"]} destrancado!', C['green'])

    def undo(self):
        if self.history and not self.opening:
            self.M, _ = self.history.pop()
            audio.sfx('ui_back')

    def reset(self):
        if not self.opening:
            audio.sfx('chain')
            self.load_lock()

    def on_event(self, e):
        for b in self.op_buttons:
            if b.handle(e):
                audio.sfx('metal_click')
                return
        for p in self.params:
            if p.handle(e):
                return
        for b in (self.apply_b, self.undo_b, self.reset_b):
            if b.handle(e):
                return

    def on_update(self, dt, paused):
        if paused:
            return
        if self.opening:
            if self.opening < 0.5 <= self.opening + dt:
                audio.sfx('creak')
                audio.sfx('metal_heavy', 0.6)
            self.opening += dt
            if self.opening > 1.6:
                self.opening = 0.0
                self.li += 1
                if self.li >= len(LOCKS):
                    self.li = len(LOCKS) - 1
                    self.opening = 99
                    self.complete()
                else:
                    self.load_lock()

    # ---------------------------------------------------------------- desenho
    def on_draw(self, surf):
        # paredes de pedra da fortaleza
        wall = self.assets.sprite('wall', 3)
        for x in range(0, W, 48):
            for y in range(40, H, 48):
                surf.blit(wall, (x, y))
        dark = pygame.Surface((W, H), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 90))
        surf.blit(dark, (0, 0))
        # área de trabalho (plano cartesiano)
        pygame.draw.rect(surf, (18, 30, 52), AREA)
        clip = surf.get_clip()
        surf.set_clip(AREA)
        for i in range(-12, 13):
            x = ORIGIN[0] + i * SCALE
            pygame.draw.line(surf, (34, 52, 84), (x, AREA.top), (x, AREA.bottom))
            y = ORIGIN[1] - i * SCALE
            pygame.draw.line(surf, (34, 52, 84), (AREA.left, y), (AREA.right, y))
        pygame.draw.line(surf, (120, 140, 180), (AREA.left, ORIGIN[1]), (AREA.right, ORIGIN[1]), 2)
        pygame.draw.line(surf, (120, 140, 180), (ORIGIN[0], AREA.top), (ORIGIN[0], AREA.bottom), 2)
        for i in range(-10, 11, 2):
            if i:
                text(surf, str(i), (ORIGIN[0] + i * SCALE, ORIGIN[1] + 6), 13, (120, 140, 180), kind='mono', center=True, shadow=False)
                text(surf, str(i), (ORIGIN[0] - 14, ORIGIN[1] - i * SCALE - 8), 13, (120, 140, 180), kind='mono', shadow=False)
        text(surf, 'x', (AREA.right - 16, ORIGIN[1] - 24), 18, (160, 180, 220))
        text(surf, 'y', (ORIGIN[0] + 8, AREA.top + 4), 18, (160, 180, 220))
        # fechadura (silhueta-alvo)
        tgt = [to_screen(p) for p in self.target_pts]
        pulse = 160 + int(80 * math.sin(self.t * 4))
        if self.opening:
            pygame.draw.polygon(surf, (pulse, 220, 120), tgt)
        else:
            s = pygame.Surface(AREA.size, pygame.SRCALPHA)
            pygame.draw.polygon(s, (240, 200, 80, 50), [(x - AREA.x, y - AREA.y) for x, y in tgt])
            surf.blit(s, AREA.topleft)
            dashed_poly(surf, (240, pulse, 80), tgt, 2, 7)
        # prévia (fantasma)
        if not self.opening:
            P, _ = self.pending()
            ghost = [to_screen(p) for p in cg.apply2(P @ self.M, KEY)]
            s = pygame.Surface(AREA.size, pygame.SRCALPHA)
            pygame.draw.polygon(s, (150, 200, 255, 60), [(x - AREA.x, y - AREA.y) for x, y in ghost])
            surf.blit(s, AREA.topleft)
            pygame.draw.polygon(surf, (150, 200, 255), ghost, 1)
        # chave atual
        cur = cg.apply2(self.M, KEY)
        pts = [to_screen(p) for p in cur]
        pygame.draw.polygon(surf, (110, 160, 240), pts)
        pygame.draw.polygon(surf, (230, 240, 255), pts, 2)
        pygame.draw.circle(surf, C['red'], to_screen(cur[0]), 5)       # vértice de referência
        pygame.draw.circle(surf, C['gold'], ORIGIN, 4)
        surf.set_clip(clip)
        pygame.draw.rect(surf, C['border'], AREA, 3)
        text(surf, 'Plano cartesiano (y para cima)   -   tela: ys = oy - y·escala', (AREA.x + 12, AREA.bottom - 26), 15, C['dim'])
        text(surf, f'{LOCKS[self.li]["name"]}  ({self.li + 1}/{len(LOCKS)})', (AREA.x + 12, AREA.y + 8), 22, C['gold'])
        self.draw_panel(surf)

    def draw_panel(self, surf):
        r = pygame.Rect(PX, 50, W - PX - 12, 650)
        panel(surf, r, alpha=238)
        L = LOCKS[self.li]
        text(surf, 'Grimório das Transformações', (r.x + 16, r.y + 10), 22, C['gold'])
        text_block(surf, L['desc'], (r.x + 16, r.y + 42, r.w - 32, 70), 16, C['parch'], kind='serif', spacing=1)
        for b in self.op_buttons:
            b.draw(surf)
        for p in self.params:
            p.draw(surf)
        if not self.params:
            text(surf, '(sem parâmetros)', (r.x + 20, 290), 17, C['dim'])
        P, name = self.pending()
        matrix_view(surf, P, (r.x + 14, 372), 15, f'Op: {name}', fmt='{:5.2f}')
        matrix_view(surf, self.M, (r.x + 228, 372), 15, 'M acumulada', C['gold'], fmt='{:5.2f}')
        text(surf, 'Histórico (M = opN · ... · op1):', (r.x + 16, 500), 16, C['gold'])
        hist = [h[1] for h in self.history][-4:]
        text(surf, '  ->  '.join(hist) if hist else '(nenhuma)', (r.x + 16, 524), 15, C['text'], kind='mono', shadow=False)
        text(surf, 'M · [x, y, 1]ᵀ aplicado a cada vértice', (r.x + 16, 560), 15, C['dim'], kind='mono')
        P2 = P @ self.M
        v = cg.apply2(P2, [KEY[0]])[0]
        text(surf, f'vértice ●: ({KEY[0][0]:.1f},{KEY[0][1]:.1f}) -> ({v[0]:.2f},{v[1]:.2f})', (r.x + 16, 584), 15, C['text'], kind='mono')
        tv = self.target_pts[0]
        text(surf, f'alvo do ●: ({tv[0]:.2f},{tv[1]:.2f})', (r.x + 16, 606), 15, C['gold'], kind='mono')
        for b in (self.apply_b, self.undo_b, self.reset_b):
            b.draw(surf)
