"""
FASE VIII - A Forja da Revolução  (Curvas -> Superfícies de revolução -> Malhas)

Para existir no 3D, Sir Lineu precisa de um corpo volumétrico. Na forja de
Volumar ele desenha o PERFIL (uma curva de Bézier cúbica) que, girado em torno
do eixo Y, gera uma superfície de revolução aproximada por uma malha de faces.
"""
import math
import numpy as np
import pygame

from engine.core import Phase, W, H
from engine.assets import text
from engine.ui import C, Button, Slider, panel, dashed_line
from engine.render3d import Renderer3D
from engine import cg, audio

EDIT = pygame.Rect(16, 50, 500, 500)
VIEW = pygame.Rect(530, 50, W - 546, 500)
INFO = pygame.Rect(16, 562, W - 32, 138)
ES = 150                                   # pixels por unidade no editor
EO = (EDIT.x + 50, EDIT.bottom - 40)       # origem (r=0, y=0) no editor
M_PROFILE = 16                              # amostras do perfil

TASKS = [
    {'name': 'Elmo Volumétrico', 'start': [(0, 2.6), (0.5, 2.2), (0.6, 1.0), (0.4, 0.3)],
     'target': [(0, 2.6), (1.5, 2.6), (1.7, 0.9), (1.2, 0.0)], 'drag': [1, 2, 3], 'color': (190, 195, 210)},
    {'name': 'Cálice Dimensional', 'start': [(0.4, 0.0), (0.6, 0.8), (0.6, 1.8), (0.4, 2.6)],
     'target': [(0.9, 0.0), (2.3, 0.6), (0.0, 1.5), (1.2, 2.7)], 'drag': [0, 1, 2, 3], 'color': (230, 190, 80)},
]


def e2s(p):
    return (EO[0] + p[0] * ES, EO[1] - p[1] * ES)


def s2e(p):
    return ((p[0] - EO[0]) / ES, (EO[1] - p[1]) / ES)


class Fase8(Phase):
    index = 7
    music = 'fase7'
    ambience = ['amb_fire']
    title = 'Fase VIII - A Forja da Revolução'
    subtitle = 'Superfícies e malhas'
    concept_title = 'Superfícies de revolução e representação por malhas'
    concept = (
        "Uma curva é percorrida por um parâmetro (u); uma SUPERFÍCIE é tecida por dois parâmetros (u, v), como "
        "latitude e longitude:   S(u,v) = ( x(u,v), y(u,v), z(u,v) ).\n\n"
        "SUPERFÍCIE DE REVOLUÇÃO: gira-se uma curva plana (o perfil) em torno de um eixo. Com o perfil (r(u), y(u)) "
        "girando em torno do eixo Y:\n"
        "   S(u, v) = ( r(u)·cos v ,  y(u) ,  r(u)·sen v ),   v ∈ [0, 2π]\n"
        "Meia-lua gera esfera, reta inclinada gera cone, onda gera vaso.\n\n"
        "Superfície matemática ≠ malha ≠ renderização. Para desenhar, amostramos u (m pontos do perfil) e v "
        "(n segmentos) e ligamos os vértices em quadriláteros: uma MALHA POLIGONAL (representação por faces / B-rep), "
        "com n·m vértices e n·(m-1) faces. Poucos segmentos deixam o objeto facetado; muitos o deixam suave, porém "
        "mais caro.\n\n"
        "O perfil aqui é uma Bézier cúbica. Arraste os pontos de controle para que ela coincida com o perfil-alvo "
        "(tracejado) e use n ≥ 16 segmentos. M alterna a exibição da malha; arraste a vista 3D para girá-la."
    )
    intro = [
        ('Ferreiro', 'smith', 'Bem-vindo à Forja da Revolução! Aqui nós não martelamos metal... nós GIRAMOS curvas.'),
        ('Volumar', 'wizard', 'Para existir no 3D, você precisa de um corpo volumétrico. Desenhe o perfil do seu elmo '
                              'com uma curva de Bézier; a forja vai girá-lo em torno do eixo Y.'),
        ('Ferreiro', 'smith', 'Siga o molde tracejado. E capriche nos segmentos: ninguém quer um elmo quadradão!'),
    ]
    outro = [
        ('Ferreiro', 'smith', 'Belíssimo trabalho! Um elmo e um cálice, cada um feito de centenas de faces.'),
        ('Volumar', 'wizard', 'Beba do Cálice Dimensional, Lineu. É hora de atravessar. Do outro lado, você verá o '
                              'mundo através de uma CÂMERA VIRTUAL - os seus próprios olhos 3D.'),
        ('Sir Lineu', 'knight', 'Vorax... estou indo até você.'),
    ]

    def setup(self):
        self.ti = 0
        self.renderer = Renderer3D(VIEW, fov=45)
        self.renderer.fog_start, self.renderer.fog_end = 50, 200
        self.ang = 30.0
        self.drag_view = False
        self.wire = True
        self.seg = Slider((INFO.x + 860, INFO.y + 50, 340, 16), 'Segmentos de revolução (n)', 3, 32, 6, 1, '{:.0f}', C['gold'])
        self.forge_b = Button((INFO.x + 860, INFO.y + 82, 340, 42), 'Forjar!', self.forge, 22, hotkey=pygame.K_RETURN,
                              color=(100, 60, 30))
        self.load()

    def load(self):
        T = TASKS[self.ti]
        self.pts = [list(p) for p in T['start']]
        self.target_curve = cg.bezier_curve(T['target'], 40)
        self.drag_i = None
        self.ok_t = 0
        self.hud_hint = 'Arraste os pontos de controle   •   M: malha   •   ENTER: forjar'

    def profile(self):
        pts = cg.bezier_curve(self.pts, M_PROFILE - 1)
        return [(max(0.0, r), y) for r, y in pts]

    def error(self):
        return cg.hausdorff(cg.bezier_curve(self.pts, 40), self.target_curve)

    def forge(self):
        if self.ok_t:
            return
        err = self.error()
        n = int(self.seg.value)
        if err >= 0.1:
            self.toast(f'O perfil não segue o molde (erro {err:.2f} ≥ 0.10).', C['red'])
        elif n < 16:
            self.toast(f'Com n = {n} a peça fica facetada! Use n ≥ 16.', C['red'])
        else:
            self.ok_t = 0.01
            audio.sfx('anvil')
            self.toast(f'{TASKS[self.ti]["name"]} forjado!', C['green'])

    def on_event(self, e):
        if self.ok_t:
            return
        if self.seg.handle(e) or self.forge_b.handle(e):
            return
        T = TASKS[self.ti]
        if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
            self.wire = not self.wire
            audio.sfx('ui_toggle')
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i in T['drag']:
                sp = e2s(self.pts[i])
                if math.hypot(e.pos[0] - sp[0], e.pos[1] - sp[1]) < 16:
                    self.drag_i = i
                    audio.sfx('ui_pluck')
                    return
            if VIEW.collidepoint(e.pos):
                self.drag_view = True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.drag_i is not None:
                audio.sfx('tools', 0.5)
            self.drag_i = None
            self.drag_view = False
        elif e.type == pygame.MOUSEMOTION:
            if self.drag_i is not None:
                r, y = s2e(e.pos)
                self.pts[self.drag_i] = [round(max(-0.5, min(2.8, r)), 2), round(max(-0.1, min(3.1, y)), 2)]
            elif self.drag_view:
                self.ang += e.rel[0] * 0.5

    def on_update(self, dt, paused):
        if not self.drag_view:
            self.ang += dt * 20
        if paused:
            return
        if self.ok_t:
            prev = self.ok_t
            self.ok_t += dt
            for tm in (0.45, 0.9):
                if prev < tm <= self.ok_t:
                    audio.sfx('anvil')
            if prev < 1.3 <= self.ok_t:
                audio.sfx('item_metal')
            if self.ok_t > 1.8:
                self.ti += 1
                if self.ti >= len(TASKS):
                    self.ti = len(TASKS) - 1
                    self.ok_t = 0
                    self.complete()
                    self.ok_t = 99
                    return
                self.load()
                self.say([('Ferreiro', 'smith', 'Agora o Cálice Dimensional! Todos os quatro pontos estão livres. '
                                                'Um perfil ondulado gera um vaso.')])

    # ---------------------------------------------------------------- desenho
    def on_draw(self, surf):
        wall = self.assets.sprite('wall2', 3)
        for x in range(0, W, 48):
            for y in range(40, H, 48):
                surf.blit(wall, (x, y))
        sh = pygame.Surface((W, H), pygame.SRCALPHA)
        sh.fill((40, 10, 0, 150))
        surf.blit(sh, (0, 0))
        self.draw_editor(surf)
        self.draw_view(surf)
        self.draw_info(surf)

    def draw_editor(self, surf):
        panel(surf, EDIT, alpha=240, fill=(30, 22, 18))
        text(surf, 'Perfil (r, y)', (EDIT.x + 14, EDIT.y + 10), 20, C['gold'])
        clip = surf.get_clip()
        surf.set_clip(EDIT.inflate(-6, -6))
        for i in range(0, 4):
            pygame.draw.line(surf, (60, 46, 36), e2s((0, i)), e2s((2.8, i)))
            text(surf, str(i), (EO[0] - 22, e2s((0, i))[1] - 8), 14, C['dim'], kind='mono', shadow=False)
        for i in range(0, 3):
            pygame.draw.line(surf, (60, 46, 36), e2s((i, -0.1)), e2s((i, 3.1)))
            text(surf, str(i), (e2s((i, 0))[0] - 4, EO[1] + 6), 14, C['dim'], kind='mono', shadow=False)
        dashed_line(surf, (120, 200, 255), e2s((0, -0.2)), e2s((0, 3.2)), 2, 8)
        text(surf, 'eixo Y (revolução)', (EO[0] + 8, EO[1] - 30), 14, (120, 200, 255))
        tg = [e2s(p) for p in self.target_curve]
        for i in range(0, len(tg) - 1, 2):
            pygame.draw.line(surf, (240, 200, 80), tg[i], tg[i + 1], 4)
        # espelho do perfil (para dar ideia da peça)
        mirror = [(EO[0] - (x - EO[0]), y) for x, y in [e2s(p) for p in self.profile()]]
        pygame.draw.lines(surf, (90, 70, 60), False, mirror, 2)
        T = TASKS[self.ti]
        cps = [e2s(p) for p in self.pts]
        for i in range(3):
            dashed_line(surf, (200, 180, 255), cps[i], cps[i + 1], 1, 6)
        curve = [e2s(p) for p in cg.bezier_curve(self.pts, 50)]
        pygame.draw.lines(surf, C['green'] if self.ok_t else (255, 255, 255), False, curve, 3)
        for p in [e2s(p) for p in self.profile()]:
            pygame.draw.circle(surf, (255, 150, 80), (int(p[0]), int(p[1])), 3)
        for i, p in enumerate(cps):
            drag = i in T['drag']
            pygame.draw.circle(surf, (20, 10, 10), (int(p[0]), int(p[1])), 11)
            pygame.draw.circle(surf, C['gold'] if drag else (160, 160, 170), (int(p[0]), int(p[1])), 9 if drag else 6)
            text(surf, f'P{i}', (p[0] + 12, p[1] - 22), 16, C['gold'] if drag else C['dim'])
        surf.set_clip(clip)

    def draw_view(self, surf):
        panel(surf, VIEW, alpha=245, fill=(16, 14, 22))
        n = int(self.seg.value)
        verts, faces = cg.revolution(self.profile(), n)
        r = self.renderer
        a = math.radians(self.ang)
        r.set_camera((5.6 * math.sin(a), 3.6, -5.6 * math.cos(a)), (0, 1.2, 0))
        r.begin()
        # base da forja
        bv, bf = cg.box(4, 0.3, 4)
        r.mesh(bv, bf, cg.T3(0, -0.25, 0), (90, 70, 60), layer=0)
        col = TASKS[self.ti]['color']
        r.mesh(verts, faces, np.eye(4), col, cull=False, outline=(40, 40, 50) if self.wire else None)
        r.render(surf)
        text(surf, TASKS[self.ti]['name'], (VIEW.x + 16, VIEW.y + 10), 22, C['gold'])
        text(surf, f'vértices: {len(verts)}   faces: {len(faces)}   (n={n}, m={M_PROFILE})',
             (VIEW.x + 16, VIEW.bottom - 30), 16, C['text'], kind='mono')

    def draw_info(self, surf):
        panel(surf, INFO, alpha=240)
        text(surf, 'S(u, v) = ( r(u)·cos v ,  y(u) ,  r(u)·sen v )', (INFO.x + 20, INFO.y + 16), 18, C['text'], kind='mono')
        text(surf, '(r(u), y(u)) = Bézier cúbica do perfil,  u em [0,1],  v em [0,2π]', (INFO.x + 20, INFO.y + 44), 16, C['dim'], kind='mono')
        err = self.error()
        text(surf, f'Erro do perfil (Hausdorff) = {err:.3f}  (meta < 0.10)', (INFO.x + 20, INFO.y + 76), 17,
             C['green'] if err < 0.1 else C['text'], kind='mono')
        cps = '  '.join(f'P{i}({p[0]:.2f},{p[1]:.2f})' for i, p in enumerate(self.pts))
        text(surf, cps, (INFO.x + 20, INFO.y + 104), 15, C['gold'], kind='mono')
        self.seg.draw(surf)
        self.forge_b.draw(surf)
