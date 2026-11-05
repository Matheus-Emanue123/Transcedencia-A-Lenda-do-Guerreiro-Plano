"""
FASE IX - Transcendência  (Câmera virtual e pipeline 3D completo)

Sir Lineu finalmente está no 3D, vendo o mundo pela câmera virtual
(lookAt + perspectiva). Ele explora o reino volumétrico, recolhe os três
Cristais Dimensionais e enfrenta Vorax, o Dragão Achatador.
"""
import math
import random
import numpy as np
import pygame

from engine.core import Phase, W, H
from engine.assets import text
from engine.ui import C, panel
from engine.render3d import Renderer3D
from engine import cg, audio

VIEW = pygame.Rect(0, 40, W, H - 40)
BOUND = 46
CASTLE = np.array([0.0, 0.0, 30.0])
EYE_H = 1.8


class Fase9(Phase):
    index = 8
    music = 'fase9'
    ambience = ['amb_field']
    title = 'Fase IX - Transcendência'
    subtitle = 'Câmera virtual'
    concept_title = 'Câmera virtual: posição, orientação e projeção'
    concept = (
        "A câmera virtual é o 'olho' do observador na cena 3D. Ela é definida por:\n"
        " • POSIÇÃO (eye): onde a câmera está;\n"
        " • PONTO FOCAL (center): para onde ela olha - o vetor eye->center é a DIREÇÃO DE PROJEÇÃO;\n"
        " • VETOR UP (view-up): qual lado é 'para cima' - define a orientação (rolagem);\n"
        " • PROJEÇÃO: aqui, perspectiva com campo de visão (FOV), razão de aspecto e planos de recorte near/far.\n\n"
        "lookAt(eye, center, up) monta a matriz de visualização V:  f = normalizar(center - eye),  s = f × up,  u = s × f.\n"
        "O pipeline deste mundo, escrito do zero:\n"
        "  vértice (SRO) -> Model -> SRU -> View(lookAt) -> recorte no plano near -> Projeção -> divisão por w (SRN) "
        "-> Viewport (SRD)\n"
        "Visibilidade: back-face culling + algoritmo do pintor. Iluminação: Lambert com sombreamento constante, + névoa.\n\n"
        "Controles: W/A/S/D andam, SETAS ou mouse (segurando o botão direito) giram a câmera, RODA do mouse altera o FOV "
        "(zoom), ESPAÇO ou clique esquerdo lança raios mágicos, C mostra/oculta os parâmetros da câmera."
    )
    intro = [
        ('Sir Lineu', 'knight', 'Eu... eu consigo ver PROFUNDIDADE! As coisas ficam menores ao longe... as torres '
                                'têm lados que eu nunca tinha visto!'),
        ('Volumar', 'wizard', 'Bem-vindo à Terceira Dimensão! Agora você vê o mundo por uma câmera virtual: uma posição, '
                              'um ponto para onde olhar e um vetor "para cima".'),
        ('Volumar', 'wizard', 'Vorax se esconde. Para forçá-lo a aparecer, recolha os três Cristais Dimensionais '
                              'espalhados pelo reino. W/A/S/D para andar, setas ou botão direito do mouse para olhar.'),
    ]
    outro = []

    def setup(self):
        self.r = Renderer3D(VIEW, fov=65, near=0.15, far=300)
        self.r.fog_color = (170, 190, 220)
        self.r.fog_start, self.r.fog_end = 30, 95
        self.pos = np.array([0.0, EYE_H, -30.0])
        self.yaw = 0.0          # 0 = olhando para +z
        self.pitch = 4.0
        self.show_cam = True
        self.build_world()
        self.crystals = [np.array(p) for p in [(-30.0, 2.2, 0.0), (32.0, 2.2, 14.0), (8.0, 2.2, 52.0)]]
        self.got = [False, False, False]
        self.state = 'explore'
        self.dragon = None
        self.bolts = []
        self.fires = []
        self.hearts = 3
        self.hurt = 0
        self.cool = 0
        self.dragon_dead = 0
        self.hud_hint = ''

    # ------------------------------------------------------------------ mundo
    def build_world(self):
        rnd = random.Random(11)
        self.static = []
        # chão: quadriculado
        n, s = 12, 8.0
        verts, faces, cols = [], [], []
        for i in range(n):
            for j in range(n):
                x0, z0 = -n * s / 2 + i * s, -n * s / 2 + j * s + 12
                b = len(verts)
                verts += [(x0, 0, z0), (x0, 0, z0 + s), (x0 + s, 0, z0 + s), (x0 + s, 0, z0)]
                faces.append((b, b + 1, b + 2, b + 3))
                cols.append((86, 160, 70) if (i + j) % 2 else (76, 146, 62))
        self.ground = (np.array(verts, dtype=float), faces, cols)
        # caminho de pedra até o castelo
        pv, pf = cg.box(4, 0.05, 40)
        self.path = (pv, pf, cg.T3(0, 0.03, 4))
        # castelo
        cyl = cg.cylinder(2.2, 9, 10)
        cone = cg.cone(2.8, 4, 10)
        for dx in (-9, 9):
            for dz in (-9, 9):
                p = CASTLE + (dx, 0, dz)
                self.static.append((cyl[0], cyl[1], cg.T3(*p), (175, 170, 165), True))
                self.static.append((cone[0], cone[1], cg.T3(p[0], 9, p[2]), (180, 60, 50), True))
        wv, wf = cg.box(14, 6, 1.6)
        for (dx, dz, ry) in [(0, -9, 0), (0, 9, 0), (-9, 0, 90), (9, 0, 90)]:
            M = cg.T3(CASTLE[0] + dx, 3, CASTLE[2] + dz) @ cg.Ry(ry)
            self.static.append((wv, wf, M, (160, 155, 150), True))
        kv, kf = cg.box(7, 12, 7)
        self.static.append((kv, kf, cg.T3(CASTLE[0], 6, CASTLE[2]), (150, 146, 140), True))
        kc = cg.cone(5.5, 5, 4)
        self.static.append((kc[0], kc[1], cg.T3(CASTLE[0], 12, CASTLE[2]) @ cg.Ry(45), (60, 70, 160), True))
        gv, gf = cg.box(4, 4.5, 0.3)
        self.static.append((gv, gf, cg.T3(CASTLE[0], 2.25, CASTLE[2] - 9.9), (90, 60, 30), True))
        # árvores
        trunk = cg.cylinder(0.35, 1.6, 6)
        leaves = cg.cone(1.8, 4.2, 7)
        self.trees = []
        while len(self.trees) < 16:
            x, z = rnd.uniform(-42, 42), rnd.uniform(-38, 58)
            if abs(x) < 16 and abs(z - CASTLE[2]) < 16:
                continue
            if abs(x) < 4 and z < 22:
                continue
            if abs(x) < 5 and abs(z + 30) < 6:
                continue
            self.trees.append((x, z))
            k = rnd.uniform(0.8, 1.3)
            self.static.append((trunk[0], trunk[1], cg.T3(x, 0, z) @ cg.S3(k, k, k), (110, 70, 40), True))
            self.static.append((leaves[0], leaves[1], cg.T3(x, 1.4 * k, z) @ cg.S3(k, k, k),
                                (40 + rnd.randint(0, 30), 120 + rnd.randint(0, 40), 50), True))
        # montanhas no horizonte
        mt = cg.cone(18, 22, 7)
        for i in range(9):
            a = i / 9 * 2 * math.pi
            x, z = 95 * math.cos(a), 12 + 95 * math.sin(a)
            self.static.append((mt[0], mt[1], cg.T3(x, 0, z) @ cg.Ry(i * 17), (110, 110, 130), True))
        self.octa = cg.octahedron(0.8)
        self.wiz16 = self.assets.sprite('wizard', 1)
        self._bb_cache = {}

    def wizard_img(self, px, flip):
        px = max(4, int(px) // 4 * 4)
        key = (px, flip)
        if key not in self._bb_cache:
            if len(self._bb_cache) > 80:
                self._bb_cache.clear()
            img = pygame.transform.scale(self.wiz16, (px, px))
            self._bb_cache[key] = pygame.transform.flip(img, True, False) if flip else img
        return self._bb_cache[key]

    def dragon_img(self, px, flip):
        return self.assets.dragon_img(max(8, int(px) // 6 * 6), flip)

    # --------------------------------------------------------------- câmera
    def forward(self):
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        return np.array([math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)])

    def on_event(self, e):
        if e.type == pygame.MOUSEWHEEL:
            self.r.set_fov(max(25, min(100, self.r.fov - e.y * 5)))
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_c:
            self.show_cam = not self.show_cam
        elif (e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE) or \
                (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
            self.shoot()
        elif e.type == pygame.MOUSEMOTION and e.buttons[2]:
            self.yaw -= e.rel[0] * 0.25
            self.pitch = max(-60, min(70, self.pitch - e.rel[1] * 0.25))

    def shoot(self):
        if self.cool > 0 or self.state == 'won':
            return
        self.cool = 0.28
        audio.sfx('bolt')
        f = self.forward()
        self.bolts.append({'p': self.pos + f * 0.8 + np.array([0, -0.3, 0]), 'v': f * 42, 't': 1.6})

    # --------------------------------------------------------------- update
    def on_update(self, dt, paused):
        t = self.t
        if self.dragon is not None and self.state != 'won':
            self.update_dragon(dt, paused)
        if paused:
            return
        self.cool -= dt
        self.hurt = max(0, self.hurt - dt)
        k = pygame.key.get_pressed()
        self.yaw += (k[pygame.K_LEFT] - k[pygame.K_RIGHT]) * 90 * dt
        self.pitch = max(-60, min(70, self.pitch + (k[pygame.K_UP] - k[pygame.K_DOWN]) * 60 * dt))
        y = math.radians(self.yaw)
        fw = np.array([math.sin(y), 0, math.cos(y)])
        rt = np.array([-math.cos(y), 0, math.sin(y)])     # f x up (direita da câmera)
        mv = fw * (k[pygame.K_w] - k[pygame.K_s]) + rt * (k[pygame.K_d] - k[pygame.K_a])
        if np.linalg.norm(mv) > 0:
            sp = 14 if (k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT]) else 9
            self.step_t = getattr(self, 'step_t', 0) - dt
            if self.step_t <= 0:
                audio.sfx('step_grass')
                self.step_t = 0.27 if sp > 9 else 0.38
            new = self.pos + mv / np.linalg.norm(mv) * sp * dt
            new[0] = max(-BOUND, min(BOUND, new[0]))
            new[2] = max(-BOUND + 12, min(BOUND + 12, new[2]))
            if not self.collide(new):
                self.pos = new
            else:
                # desliza em um dos eixos
                for ax in (0, 2):
                    cand = self.pos.copy()
                    cand[ax] = new[ax]
                    if not self.collide(cand):
                        self.pos = cand
                        break
        self.pos[1] = EYE_H + 0.06 * math.sin(t * 9) * (np.linalg.norm(mv) > 0)
        # cristais
        if self.state == 'explore':
            for i, c in enumerate(self.crystals):
                if not self.got[i] and np.linalg.norm((self.pos - c)[[0, 2]]) < 2.6:
                    self.got[i] = True
                    audio.sfx('gem2')
                    audio.sfx('powerup')
                    n = sum(self.got)
                    self.toast(f'Cristal Dimensional {n}/3 recolhido!', C['green'])
                    if n == 3:
                        self.state = 'battle'
                        self.spawn_dragon()
                        audio.music('boss')
                        audio.sfx('roar')
                        audio.sfx('wings')
                        self.say([('Vorax', 'dragon', 'VOCÊ?! Um ser plano no MEU espaço? Eu esmaguei seu reino até '
                                                      'virar pixels... e farei o mesmo com você!'),
                                  ('Volumar', 'wizard', 'Mire com a câmera, Lineu! O centro da tela é a direção de projeção. '
                                                        'ESPAÇO ou clique lança os raios. Desvie das bolas de fogo andando!'),
                                  ('Sir Lineu', 'knight', 'Por Planícia... e pela Terceira Dimensão!')])
        # projéteis do jogador
        for b in self.bolts:
            b['p'] = b['p'] + b['v'] * dt
            b['t'] -= dt
            if self.dragon is not None and self.state == 'battle':
                if np.linalg.norm(b['p'] - self.dragon['p']) < 3.6:
                    b['t'] = 0
                    self.dragon['hp'] -= 1
                    audio.sfx('bolt_hit')
                    audio.sfx('dragon_hurt', 0.8)
                    self.dragon['flash'] = 0.25
                    if self.dragon['hp'] <= 0:
                        self.state = 'won'
                        self.dragon_dead = 0.01
                        audio.sfx('dragon_die')
                        audio.sfx('explosion', 0.8)
                        self.toast('Vorax foi derrotado!', C['gold'], 4)
        self.bolts = [b for b in self.bolts if b['t'] > 0 and b['p'][1] > 0]
        # bolas de fogo do dragão
        for f in self.fires:
            f['p'] = f['p'] + f['v'] * dt
            f['t'] -= dt
            if np.linalg.norm(f['p'] - self.pos) < 1.3:
                f['t'] = 0
                self.hearts -= 1
                audio.sfx('hurt')
                self.hurt = 0.5
                if self.hearts <= 0:
                    self.toast('Você foi achatado! A batalha recomeça.', C['red'], 3)
                    self.hearts = 3
                    self.pos = np.array([0.0, EYE_H, -30.0])
                    self.yaw, self.pitch = 0.0, 8.0
                    self.dragon['hp'] = self.dragon['max']
                    self.fires = []
                    break
        self.fires = [f for f in self.fires if f['t'] > 0 and f['p'][1] > -0.5]
        if self.dragon_dead:
            if self.dragon_dead < 1.6 <= self.dragon_dead + dt:
                audio.sfx('thud')
                audio.sfx('victory')
            self.dragon_dead += dt
            if self.dragon_dead > 3.5:
                self.dragon_dead = 0
                self.complete()

    def collide(self, p):
        for dx in (-9, 9):
            for dz in (-9, 9):
                if math.hypot(p[0] - (CASTLE[0] + dx), p[2] - (CASTLE[2] + dz)) < 3.0:
                    return True
        if abs(p[0] - CASTLE[0]) < 10.2 and abs(p[2] - CASTLE[2]) < 10.2:
            return True
        for x, z in self.trees:
            if math.hypot(p[0] - x, p[2] - z) < 0.9:
                return True
        return False

    def spawn_dragon(self):
        self.dragon = {'a': 0.0, 'p': CASTLE + np.array([0, 12, -20.0]), 'hp': 10, 'max': 10, 'fire_t': 3.0,
                       'flash': 0, 'vx': 1}

    def update_dragon(self, dt, paused):
        d = self.dragon
        if self.state == 'won':
            return
        if paused:
            dt = dt * 0.3
        d['a'] += dt * 0.35
        R = 22
        old = d['p'].copy()
        d['p'] = CASTLE + np.array([R * math.sin(d['a']), 10 + 2.5 * math.sin(d['a'] * 3), -R * math.cos(d['a']) * 0.8])
        d['vel'] = (d['p'] - old) / max(dt, 1e-6)
        d['flash'] = max(0, d['flash'] - dt)
        if paused:
            return
        dist = float(np.linalg.norm(d['p'] - self.pos))
        near = max(0.2, min(1.0, 1.2 - dist / 45))
        d['wing_t'] = d.get('wing_t', 1.0) - dt
        if d['wing_t'] <= 0:
            audio.sfx(random.choice(('wings', 'wings2')), near)
            d['wing_t'] = random.uniform(1.6, 2.4)
        d['roar_t'] = d.get('roar_t', 8.0) - dt
        if d['roar_t'] <= 0:
            audio.sfx('roar', near)
            d['roar_t'] = random.uniform(7, 12)
        d['fire_t'] -= dt
        if d['fire_t'] <= 0:
            d['fire_t'] = max(1.2, 2.6 - 0.12 * (d['max'] - d['hp']))
            target = self.pos + np.array([0, -0.4, 0])
            v = cg.normalize(target - d['p']) * 15
            self.fires.append({'p': d['p'].copy(), 'v': v, 't': 5})
            audio.sfx('fireball', near)
            if random.random() < 0.35:
                audio.sfx('growl', near)

    # --------------------------------------------------------------- desenho
    def on_draw(self, surf):
        # céu (gradiente) - o "fundo" antes da cena
        top, bot = (70, 120, 200), self.r.fog_color
        for i in range(0, VIEW.h, 4):
            tt = i / VIEW.h
            c = tuple(int(top[k] + (bot[k] - top[k]) * min(1, tt * 1.6)) for k in range(3))
            pygame.draw.rect(surf, c, (0, VIEW.y + i, W, 4))
        f = self.forward()
        eye = self.pos
        center = eye + f
        r = self.r
        r.set_camera(eye, center, (0, 1, 0))
        r.begin()
        gv, gf, gc = self.ground
        r.mesh(gv, gf, np.eye(4), (80, 150, 70), layer=0, colors=gc)
        r.mesh(self.path[0], self.path[1], self.path[2], (170, 150, 120), layer=0.5)
        for v, fc, M, col, cull in self.static:
            r.mesh(v, fc, M, col, cull=cull)
        # cristais girando
        for i, c in enumerate(self.crystals):
            if not self.got[i]:
                M = cg.T3(c[0], c[1] + 0.4 * math.sin(self.t * 2 + i), c[2]) @ cg.Ry(self.t * 90)
                r.mesh(self.octa[0], self.octa[1], M, (120, 220, 255), light=True)
                r.sphere(c + np.array([0, 0, 0]), 0.25, (180, 240, 255))
        # Volumar (billboard) perto do início
        if True:
            r.billboard((4.0, 1.0, -22.0), self.wizard_img, 2.0)
        # dragão (billboard com a arte 2D!)
        if self.dragon is not None:
            d = self.dragon
            p = d['p'].copy()
            if self.dragon_dead:
                p[1] = max(1.5, p[1] - self.dragon_dead * 4)
            vel = d.get('vel', np.array([1.0, 0, 0]))
            a = r.billboard(p, self.dragon_img, 7.0, flip=self.screen_dir(p, vel) > 0)
            sh = cg.box(5, 0.02, 2.5)
            r.mesh(sh[0], sh[1], cg.T3(p[0], 0.04, p[2]), (40, 70, 40), layer=0.6, light=False)
        for b in self.bolts:
            r.sphere(b['p'], 0.22, (140, 220, 255))
        for fb in self.fires:
            r.sphere(fb['p'], 0.6, (255, 120, 30))
        r.render(surf)
        if self.dragon is not None and self.dragon['flash'] > 0:
            fl = pygame.Surface(VIEW.size, pygame.SRCALPHA)
            fl.fill((255, 255, 255, 40))
            surf.blit(fl, VIEW.topleft)
        self.draw_hud(surf)

    def screen_dir(self, p, vel):
        a = (np.append(p, 1) @ self.r.V.T)[0]
        b = (np.append(p + vel * 0.1, 1) @ self.r.V.T)[0]
        return b - a

    def draw_hud(self, surf):
        cx, cy = VIEW.center
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), 10, 1)
        pygame.draw.line(surf, (255, 255, 255), (cx - 16, cy), (cx - 5, cy))
        pygame.draw.line(surf, (255, 255, 255), (cx + 5, cy), (cx + 16, cy))
        pygame.draw.line(surf, (255, 255, 255), (cx, cy - 16), (cx, cy - 5))
        pygame.draw.line(surf, (255, 255, 255), (cx, cy + 5), (cx, cy + 16))
        if self.hurt > 0:
            s = pygame.Surface(VIEW.size, pygame.SRCALPHA)
            s.fill((255, 40, 20, int(160 * self.hurt)))
            surf.blit(s, VIEW.topleft)
        # cristais e corações
        for i in range(3):
            col = (120, 220, 255) if self.got[i] else (60, 60, 80)
            x = 24 + i * 34
            pygame.draw.polygon(surf, col, [(x, 56), (x + 10, 70), (x, 84), (x - 10, 70)])
            pygame.draw.polygon(surf, (255, 255, 255), [(x, 56), (x + 10, 70), (x, 84), (x - 10, 70)], 1)
        for i in range(3):
            col = (230, 50, 60) if i < self.hearts else (60, 40, 40)
            x, y = 24 + i * 34, 100
            pygame.draw.circle(surf, col, (x - 5, y), 7)
            pygame.draw.circle(surf, col, (x + 5, y), 7)
            pygame.draw.polygon(surf, col, [(x - 12, y + 2), (x + 12, y + 2), (x, y + 16)])
        if self.dragon is not None and self.state != 'won':
            d = self.dragon
            bw = 420
            r = pygame.Rect(W // 2 - bw // 2, 56, bw, 18)
            pygame.draw.rect(surf, (30, 10, 10), r, border_radius=4)
            pygame.draw.rect(surf, (200, 40, 40), (r.x, r.y, int(bw * d['hp'] / d['max']), r.h), border_radius=4)
            pygame.draw.rect(surf, C['gold'], r, 2, border_radius=4)
            text(surf, 'VORAX, O ACHATADOR', (W // 2, 80), 18, C['gold'], center=True)
        elif self.state == 'explore':
            text(surf, 'Recolha os 3 Cristais Dimensionais (veja o mapa)', (W // 2, 56), 20, C['parch'], center=True)
        self.draw_minimap(surf)
        if self.show_cam:
            r = pygame.Rect(14, H - 176, 420, 162)
            panel(surf, r, alpha=200)
            f = self.forward()
            c = self.pos + f
            text(surf, 'Câmera virtual - lookAt(eye, center, up)', (r.x + 14, r.y + 10), 17, C['gold'])
            text(surf, f'eye    = ({self.pos[0]:6.1f}, {self.pos[1]:5.2f}, {self.pos[2]:6.1f})', (r.x + 14, r.y + 38), 16, C['text'], kind='mono')
            text(surf, f'center = ({c[0]:6.1f}, {c[1]:5.2f}, {c[2]:6.1f})', (r.x + 14, r.y + 60), 16, C['text'], kind='mono')
            text(surf, 'up     = (   0.0,  1.00,    0.0)', (r.x + 14, r.y + 82), 16, C['text'], kind='mono')
            text(surf, f'FOV = {self.r.fov:.0f}°  near = {self.r.near}  far = {self.r.far:.0f}', (r.x + 14, r.y + 104), 16, C['parch'], kind='mono')
            text(surf, f'faces: {self.r.stats["faces"]}  desenhadas: {self.r.stats["drawn"]}', (r.x + 14, r.y + 126), 15, C['dim'], kind='mono')

    def draw_minimap(self, surf):
        r = pygame.Rect(W - 194, 50, 180, 180)
        panel(surf, r, alpha=200, radius=6)
        win = (BOUND, -BOUND, -BOUND + 12, BOUND + 12)     # x invertido: visto de cima
        vp = (r.x + 8, r.y + 8, r.w - 16, r.h - 16)

        def m(x, z):
            # mapa visto de cima: x -> direita, z -> para cima (SRU -> SRD)
            p = cg.sru_to_srd(x, z, win, vp)
            return (int(p[0]), int(p[1]))
        cr = pygame.Rect(0, 0, 26, 26)
        cr.center = m(CASTLE[0], CASTLE[2])
        pygame.draw.rect(surf, (150, 146, 140), cr)
        for x, z in self.trees:
            pygame.draw.circle(surf, (50, 130, 60), m(x, z), 3)
        for i, c in enumerate(self.crystals):
            if not self.got[i]:
                pygame.draw.circle(surf, (120, 220, 255), m(c[0], c[2]), 5)
        if self.dragon is not None:
            pygame.draw.circle(surf, (220, 50, 40), m(self.dragon['p'][0], self.dragon['p'][2]), 6)
        p = m(self.pos[0], self.pos[2])
        y = math.radians(self.yaw)
        tip = (p[0] - 10 * math.sin(y), p[1] - 10 * math.cos(y))
        pygame.draw.line(surf, C['gold'], p, tip, 2)
        pygame.draw.circle(surf, C['gold'], p, 4)
