"""
FASE VII - O Limiar da Profundidade  (Projeções geométricas)

Um Cristal Dimensional flutua no limiar entre 2D e 3D. Sir Lineu só enxerga
sua PROJEÇÃO no plano de Planícia. Girando o objeto 3D (e escolhendo entre
projeção ortográfica e perspectiva), ele precisa fazer a projeção coincidir
com a silhueta da fechadura.
"""
import math
import numpy as np
import pygame

from engine.core import Phase, W, H
from engine.assets import text, text_block
from engine.ui import C, panel, matrix_view, dashed_line
from engine import cg, audio

VIEW3D = pygame.Rect(16, 50, 620, 420)
PLANE2D = pygame.Rect(648, 50, 616, 420)
INFO = pygame.Rect(16, 482, W - 32, 218)
ZC = 4.0          # distância do objeto ao centro de projeção (modo perspectiva)
S2D = 95          # pixels por unidade no plano 2D


def rot(rx, ry, rz):
    return cg.Rz(rz) @ cg.Rx(rx) @ cg.Ry(ry)


CHALLENGES = [
    {'shape': 'cube', 'mode': 'ortho', 'rot': (0, 0, 0), 'd': 4, 'start': (25, 35, 10),
     'name': 'A Porta Quadrada',
     'desc': 'Projeção ORTOGRÁFICA: os raios projetantes são paralelos entre si e perpendiculares ao plano. '
             'Gire o cubo até que sua sombra seja um quadrado perfeito.'},
    {'shape': 'cube', 'mode': 'ortho', 'rot': (35.264, 45, 0), 'd': 4, 'start': (0, 0, 0),
     'name': 'O Selo Hexagonal',
     'desc': 'Um cubo pode projetar um HEXÁGONO! Olhe-o pela diagonal principal: gire 45° em Y e ~35° em X.'},
    {'shape': 'pyramid', 'mode': 'ortho', 'rot': (0, 0, 0), 'd': 4, 'start': (60, 25, 30),
     'name': 'A Fenda Triangular',
     'desc': 'Agora uma pirâmide de base quadrada. Encontre a orientação cuja projeção é o triângulo da fechadura.'},
    {'shape': 'cube', 'mode': 'persp', 'rot': (0, 0, 0), 'd': 3.0, 'start': (0, 30, 0),
     'name': 'O Túnel do Limiar',
     'desc': 'Esta fechadura tem um quadrado DENTRO de outro: isso só acontece na projeção PERSPECTIVA, em que objetos '
             'mais distantes ficam menores. Pressione P e ajuste a distância focal d (W/S).'},
]


def shape_data(name):
    if name == 'cube':
        return cg.cube_edges()
    if name == 'pyramid':
        return cg.pyramid_edges()
    return cg.prism_edges()


def project(verts, mode, d):
    if mode == 'ortho':
        return cg.proj_ortografica(verts)
    v = [(x, y, z + ZC) for x, y, z in verts]
    return cg.proj_perspectiva(v, d)


class Fase7(Phase):
    index = 6
    music = 'fase7'
    ambience = ['amb_dimension']
    title = 'Fase VII - O Limiar da Profundidade'
    subtitle = 'Projeções geométricas'
    concept_title = 'Projeção paralela ortográfica x projeção perspectiva'
    concept = (
        "Projetar é 'esmagar' o mundo 3D num plano 2D. Elementos: o OBJETO, o PLANO DE PROJEÇÃO, os RAIOS PROJETANTES "
        "e o CENTRO DE PROJEÇÃO (o observador).\n\n"
        "PARALELA ORTOGRÁFICA: centro de projeção no infinito; raios paralelos e perpendiculares ao plano. Preserva "
        "medidas e paralelismo (desenho técnico, CAD, jogos isométricos).  No plano z = 0:  (x, y, z) -> (x, y)\n"
        "  M_ort = [1 0 0 0; 0 1 0 0; 0 0 0 0; 0 0 0 1]\n\n"
        "PERSPECTIVA: raios convergem para o centro de projeção. Objetos distantes ficam menores (escorço) e retas "
        "paralelas convergem em pontos de fuga - é como o olho e as câmeras funcionam.\n"
        "  Centro na origem e plano em z = d:   x' = d·x/z   y' = d·y/z\n"
        "  M_per = [1 0 0 0; 0 1 0 0; 0 0 1 0; 0 0 1/d 0]  ->  divide-se por w = z/d (coordenada homogênea!)\n\n"
        "Controles: SETAS giram em X e Y, Q/E giram em Z (SHIFT = devagar), P alterna a projeção, W/S mudam d, "
        "R zera a rotação. A projeção precisa coincidir com a silhueta dourada (distância de Hausdorff < 0.12)."
    )
    intro = [
        ('Volumar', 'wizard', 'Este é o Limiar da Profundidade. Do seu lado, Lineu, você só enxerga a SOMBRA dos '
                              'objetos 3D - a projeção deles no seu plano.'),
        ('Volumar', 'wizard', 'À esquerda está o que EU vejo: o cristal no espaço, os raios projetantes e o plano de '
                              'Planícia. À direita, o que VOCÊ vê. Gire o cristal até a sombra encaixar na fechadura.'),
        ('Sir Lineu', 'knight', 'Então é assim que um ser 3D aparece no meu mundo... como uma sombra que muda de forma!'),
    ]
    outro = [
        ('Volumar', 'wizard', 'Você viu o túnel em perspectiva: as coisas longe ficam menores. Pela primeira vez, '
                              'você PERCEBEU profundidade.'),
        ('Sir Lineu', 'knight', 'Sinto meu corpo... estranho. Como se eu tivesse um "lado de dentro".'),
        ('Volumar', 'wizard', 'Falta pouco. Um ser 3D precisa de um corpo 3D. Vamos à Forja: você vai modelar sua '
                              'própria armadura volumétrica a partir de uma curva.'),
    ]

    def setup(self):
        self.ci = 0
        self.load()

    def load(self):
        ch = CHALLENGES[self.ci]
        self.verts, self.edges = shape_data(ch['shape'])
        self.rx, self.ry, self.rz = ch['start']
        self.mode = 'ortho'
        self.d = 5.0 if ch['mode'] == 'persp' else 4.0
        self.target = project(cg.apply4(rot(*ch['rot']), self.verts), ch['mode'], ch['d'])
        self.ok_t = 0
        self.hud_hint = 'SETAS / Q E: girar   •   P: projeção   •   W/S: distância d   •   R: zerar'

    def current(self):
        v = cg.apply4(rot(self.rx, self.ry, self.rz), self.verts)
        return v, project(v, self.mode, self.d)

    def on_event(self, e):
        if e.type == pygame.KEYDOWN and not self.ok_t:
            if e.key == pygame.K_p:
                audio.sfx('ui_switch')
                audio.sfx('forcefield', 0.6)
                self.mode = 'persp' if self.mode == 'ortho' else 'ortho'
            elif e.key == pygame.K_r:
                self.rx = self.ry = self.rz = 0
                audio.sfx('ui_back')

    def on_update(self, dt, paused):
        if paused:
            return
        if self.ok_t:
            audio.get().loop('hum_rotate', False)
            self.ok_t += dt
            if self.ok_t > 1.8:
                self.ci += 1
                if self.ci >= len(CHALLENGES):
                    self.ci = len(CHALLENGES) - 1
                    self.complete()
                    self.ok_t = 0
                    return
                self.load()
            return
        k = pygame.key.get_pressed()
        sp = (15 if (k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT]) else 70) * dt
        self.ry += (k[pygame.K_RIGHT] - k[pygame.K_LEFT]) * sp
        self.rx += (k[pygame.K_DOWN] - k[pygame.K_UP]) * sp
        self.rz += (k[pygame.K_e] - k[pygame.K_q]) * sp
        rotating = any(k[x] for x in (pygame.K_RIGHT, pygame.K_LEFT, pygame.K_UP, pygame.K_DOWN, pygame.K_q, pygame.K_e))
        audio.get().loop('hum_rotate', rotating, 0.6 if sp < 1 else 1.0)
        if self.mode == 'persp':
            old = self.d
            self.d = max(1.0, min(8.0, self.d + (k[pygame.K_w] - k[pygame.K_s]) * dt * (0.4 if sp < 1 else 1.5)))
            if int(old * 10) != int(self.d * 10):
                audio.sfx('ui_scroll')
        _, p = self.current()
        self.err = cg.hausdorff(p, self.target)
        if self.err < 0.12:
            self.ok_t = 0.01
            audio.get().loop('hum_rotate', False)
            audio.sfx('lock')
            audio.sfx('forcefield')
            self.toast(f'{CHALLENGES[self.ci]["name"]}: a sombra encaixou!', C['green'])

    # ---------------------------------------------------------------- desenho
    def on_draw(self, surf):
        surf.fill((14, 10, 26))
        for i in range(90):
            x, y = (i * 7919) % W, 40 + (i * 104729) % (H - 40)
            surf.fill((80, 70, 120), (x, y, 2, 2))
        self.draw_3d(surf)
        self.draw_2d(surf)
        self.draw_info(surf)

    def draw_3d(self, surf):
        panel(surf, VIEW3D, alpha=235, fill=(20, 16, 36))
        text(surf, 'Visão de Volumar (3D)', (VIEW3D.x + 14, VIEW3D.y + 10), 20, C['purple'])
        V = cg.look_at((6.5, 4.5, -9.0), (0, 0, 1.0), (0, 1, 0))
        P = cg.perspective(45, VIEW3D.w / VIEW3D.h, 0.1, 100)
        M = P @ V

        def scr(pts):
            out = cg.apply4(M, np.asarray(pts, dtype=float))
            return [(VIEW3D.x + (x + 1) * 0.5 * VIEW3D.w, VIEW3D.y + (1 - (y + 1) * 0.5) * VIEW3D.h) for x, y, _ in out]

        v3, p2 = self.current()
        if self.mode == 'ortho':
            zp = 3.2
            cop = None
        else:
            zp = self.d - ZC
            cop = (0, 0, -ZC)
        # plano de projeção (Planícia)
        sz = 3.0
        quad = scr([(-sz, -sz, zp), (sz, -sz, zp), (sz, sz, zp), (-sz, sz, zp)])
        s = pygame.Surface(VIEW3D.size, pygame.SRCALPHA)
        pygame.draw.polygon(s, (90, 255, 120, 40), [(x - VIEW3D.x, y - VIEW3D.y) for x, y in quad])
        surf.blit(s, VIEW3D.topleft)
        pygame.draw.polygon(surf, (90, 255, 120), quad, 1)
        # raios projetantes
        onplane = [(x, y, zp) for x, y in p2]
        a = scr(v3)
        b = scr(onplane)
        if cop is None:
            for i in range(len(v3)):
                dashed_line(surf, (170, 120, 230), a[i], b[i], 1, 6)
        else:
            c = scr([cop])[0]
            for i in range(len(v3)):
                far = b[i] if v3[i][2] + ZC < self.d else a[i]
                dashed_line(surf, (170, 120, 230), c, far, 1, 6)
            pygame.draw.circle(surf, C['gold'], (int(c[0]), int(c[1])), 6)
            text(surf, 'centro de projeção', (c[0] + 8, c[1] - 6), 14, C['gold'])
        for i, j in self.edges:
            pygame.draw.line(surf, C['gold'], b[i], b[j], 2)
        for i, j in self.edges:
            pygame.draw.line(surf, (235, 235, 255), a[i], a[j], 2)
        text(surf, 'plano de projeção', (quad[2][0] - 10, quad[2][1] - 22), 14, (90, 255, 120))
        text(surf, f'rotX={self.rx % 360:6.1f}°  rotY={self.ry % 360:6.1f}°  rotZ={self.rz % 360:6.1f}°',
             (VIEW3D.x + 14, VIEW3D.bottom - 28), 15, C['text'], kind='mono')

    def draw_2d(self, surf):
        panel(surf, PLANE2D, alpha=235, fill=(6, 20, 10))
        text(surf, 'Plano de Planícia (2D)', (PLANE2D.x + 14, PLANE2D.y + 10), 20, (90, 255, 120))
        cx, cy = PLANE2D.centerx, PLANE2D.centery + 10
        pygame.draw.line(surf, (30, 70, 40), (PLANE2D.x + 10, cy), (PLANE2D.right - 10, cy))
        pygame.draw.line(surf, (30, 70, 40), (cx, PLANE2D.y + 40), (cx, PLANE2D.bottom - 10))
        f = lambda p: (cx + p[0] * S2D, cy - p[1] * S2D)
        tgt = [f(p) for p in self.target]
        pulse = 170 + int(80 * math.sin(self.t * 4))
        for i, j in self.edges:
            dashed_line(surf, (240, pulse, 80), tgt[i], tgt[j], 3, 8)
        _, p2 = self.current()
        cur = [f(p) for p in p2]
        col = C['green'] if self.ok_t else (120, 220, 255)
        for i, j in self.edges:
            pygame.draw.line(surf, col, cur[i], cur[j], 2)
        for p in cur:
            pygame.draw.circle(surf, col, (int(p[0]), int(p[1])), 3)
        kn = self.assets.sprite('knight', 3)
        surf.blit(kn, (PLANE2D.x + 20, PLANE2D.bottom - 64))

    def draw_info(self, surf):
        panel(surf, INFO, alpha=240)
        ch = CHALLENGES[self.ci]
        text(surf, f'Fechadura {self.ci + 1}/{len(CHALLENGES)}: {ch["name"]}', (INFO.x + 20, INFO.y + 12), 22, C['gold'])
        text_block(surf, ch['desc'], (INFO.x + 20, INFO.y + 46, 560, 100), 17, C['parch'], kind='serif', spacing=2)
        modo = 'ORTOGRÁFICA' if self.mode == 'ortho' else 'PERSPECTIVA'
        text(surf, f'Projeção atual: {modo}' + (f'   d = {self.d:.2f}' if self.mode == 'persp' else ''),
             (INFO.x + 20, INFO.y + 150), 18, C['text'])
        err = getattr(self, 'err', 9)
        text(surf, f'Hausdorff(sombra, fechadura) = {err:.3f}   (meta < 0.12)', (INFO.x + 20, INFO.y + 178), 16,
             C['green'] if err < 0.12 else C['dim'], kind='mono')
        if self.mode == 'ortho':
            Mx = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 1]]
            matrix_view(surf, Mx, (INFO.x + 640, INFO.y + 18), 16, 'M ortográfica', fmt='{:5.2f}')
            text(surf, "(x, y, z) -> (x, y)", (INFO.x + 640, INFO.y + 150), 17, C['text'], kind='mono')
        else:
            Mp = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 1 / self.d, 0]]
            matrix_view(surf, Mp, (INFO.x + 640, INFO.y + 18), 16, 'M perspectiva', fmt='{:5.2f}')
            text(surf, "x' = d·x/z   y' = d·y/z", (INFO.x + 640, INFO.y + 150), 17, C['text'], kind='mono')
        R = rot(self.rx, self.ry, self.rz)[:3, :3]
        matrix_view(surf, R, (INFO.x + 930, INFO.y + 18), 16, 'Rotação Rz·Rx·Ry', fmt='{:5.2f}')
