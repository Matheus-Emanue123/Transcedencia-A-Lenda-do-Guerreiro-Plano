"""
FASE IX - Transcendência  (Câmera virtual e pipeline 3D completo)

Sir Lineu finalmente está no 3D, vendo o mundo pela câmera virtual
(lookAt + perspectiva). Ele explora o reino volumétrico - castelos, moinho,
lago, montanhas - e os REINOS ACHATADOS por Vorax: vilarejos 2D deitados no
chão, onde os planicianos (sprites 2D) continuam andando. Depois de recolher
os três Cristais Dimensionais, enfrenta Vorax, agora um modelo 3D.

Técnicas: modelos OBJ simplificados + LOD, back-face culling, algoritmo do
pintor, Lambert + névoa, mapeamento de textura com perspectiva correta (os
reinos 2D no chão) e deformação de vértices animada (a cauda de Vorax).
"""
import math
import random
import numpy as np
import pygame

from engine.core import Phase, W, H
from engine.assets import text
from engine.ui import C, panel
from engine.render3d import Renderer3D
from engine import cg, audio, scenery
from engine import model as MDL

VIEW = pygame.Rect(0, 40, W, H - 40)
BOUND = 46
CASTLE = np.array([0.0, 0.0, 30.0])
LAKE = (24.0, 4.0, 10.5, 7.5)            # centro x, z e semi-eixos
EYE_H = 1.8
VOLUMAR_POS = np.array([4.0, 0.0, -22.0])
DRAGON_SCALE = 9.0
STRETCH = 2.8          # alongamento anamórfico: o desenho no chão fica legível da altura dos olhos

# reinos achatados: nome, centro (x, z), largura, construtor da imagem
KINGDOMS = [
    {'name': 'Vila de Planícia (achatada)', 'c': (-27.0, -4.0), 'w': 22.0, 'kind': 'village'},
    {'name': 'Castelo de Planícia (achatado)', 'c': (12.0, 55.0), 'w': 24.0, 'kind': 'castle'},
    {'name': 'Fazenda Plana (achatada)', 'c': (30.0, -20.0), 'w': 15.0, 'kind': 'farm'},
]
PEOPLE = ['princess', 'smith', 'scout', 'king', 'knight2', 'slime', 'illusionist', 'demon']


def surf_to_rgba(s):
    rgb = pygame.surfarray.array3d(s)
    a = pygame.surfarray.array_alpha(s)
    return np.dstack([rgb, a]).astype(np.uint8)


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
        "Pipeline deste mundo, escrito do zero: vértice (SRO) -> Model -> SRU -> View(lookAt) -> recorte near -> "
        "Projeção -> divisão por w (SRN) -> Viewport (SRD).\n"
        "Modelos OBJ (representação por faces) simplificados por agrupamento de vértices, com nível de detalhe (LOD) "
        "pela distância. Visibilidade: back-face culling + algoritmo do pintor. Iluminação: Lambert + névoa.\n"
        "Os reinos achatados são TEXTURAS 2D mapeadas no chão com perspectiva correta (um raio por pixel). "
        "A cauda de Vorax ondula por deformação de vértices (como um vertex shader).\n\n"
        "Controles: W/A/S/D andam, o MOUSE gira a câmera (M solta/prende o mouse; as SETAS também giram), RODA do mouse altera o FOV "
        "(zoom), ESPAÇO ou clique esquerdo lança raios mágicos, C mostra/oculta os parâmetros da câmera."
    )
    intro = [
        ('Sir Lineu', 'knight', 'Eu... eu consigo ver PROFUNDIDADE! As coisas ficam menores ao longe... as torres '
                                'têm lados que eu nunca tinha visto!'),
        ('Volumar', 'wizard', 'Bem-vindo à Terceira Dimensão! Agora você vê o mundo por uma câmera virtual: uma posição, '
                              'um ponto para onde olhar e um vetor "para cima".'),
        ('Volumar', 'wizard', 'Olhe ao redor: aqueles desenhos no chão são reinos que Vorax ACHATOU. Recolha os três '
                              'Cristais Dimensionais para forçá-lo a aparecer. W/A/S/D andam e o mouse olha ao redor.'),
    ]
    outro = []

    def setup(self):
        self.r = Renderer3D(VIEW, fov=65, near=0.15, far=400)
        self.r.fog_color = (182, 200, 228)
        self.r.fog_start, self.r.fog_end = 45, 160
        self.r.light = cg.normalize((0.55, 0.62, 0.55))
        self.r.ambient = 0.42
        self.pos = np.array([0.0, EYE_H, -30.0])
        self.yaw = 0.0          # 0 = olhando para +z
        self.pitch = 4.0
        self.show_cam = True
        self.mouse_lock = True        # mouse capturado: mover o mouse gira a câmera (estilo FPS)
        self._grabbed = False
        self._skip_motion = 0
        self.build_world()
        self.crystals = [np.array(p) for p in [(-30.0, 2.2, 0.5), (34.0, 2.2, 15.0), (8.0, 2.2, 52.0)]]
        self.got = [False, False, False]
        self.state = 'explore'
        self.dragon = None
        self.bolts = []
        self.fires = []
        self.hearts = 3
        self.hurt = 0
        self.cool = 0
        self.dragon_dead = 0
        self.seen_flat = False
        self.hud_hint = ''

    # ------------------------------------------------------------------ mundo
    def build_world(self):
        rnd = random.Random(11)
        L = MDL.load
        self.props = []          # (modelo, matriz, (x, z), raio_colisão, cull)
        self.colliders = []      # (x, z, raio)

        def add(name, x, z, s, ry=0.0, sy=None, col=0.0, cull=True, y=0.0):
            m = L(name)
            M = cg.T3(x, y, z) @ cg.Ry(ry) @ cg.S3(s, s if sy is None else sy, s)
            self.props.append((m, M, (x, z), cull))
            if col:
                self.colliders.append((x, z, col))
            return M

        # chão próximo: lajotas com variação de verde + chão distante gigante
        n, s = 8, 12.0
        verts, faces, cols = [], [], []
        for i in range(n):
            for j in range(n):
                x0, z0 = -n * s / 2 + i * s, -n * s / 2 + j * s + 12
                b = len(verts)
                verts += [(x0, 0, z0), (x0, 0, z0 + s), (x0 + s, 0, z0 + s), (x0 + s, 0, z0)]
                faces.append((b, b + 1, b + 2, b + 3))
                g = rnd.randint(-8, 8)
                cols.append((88 + g, 162 + g, 72 + g // 2))
        self.ground = (np.array(verts, dtype=float), faces, cols)
        fv = np.array([(-400, -0.05, -400), (-400, -0.05, 400), (400, -0.05, 400), (400, -0.05, -400)], dtype=float)
        self.far_ground = (fv, [(0, 1, 2, 3)])
        pv, pf = cg.box(3.6, 0.04, 44)
        self.path = (pv, pf, cg.T3(0, 0.02, 0))
        # lago (leque de triângulos com margem de areia)
        cx, cz, ax, az = LAKE
        N = 28
        wv, sv = [(cx, 0.03, cz)], [(cx, 0.015, cz)]
        for i in range(N):
            a = 2 * math.pi * i / N
            k = 1 + 0.08 * math.sin(3 * a) + 0.05 * math.cos(5 * a)
            wv.append((cx + ax * k * math.cos(a), 0.03, cz + az * k * math.sin(a)))
            sv.append((cx + (ax + 1.4) * k * math.cos(a), 0.015, cz + (az + 1.4) * k * math.sin(a)))
        self.lake_faces = [(0, 1 + (i + 1) % N, 1 + i) for i in range(N)]
        self.lake_v = np.array(wv, dtype=float)
        self.shore_v = np.array(sv, dtype=float)
        # castelo central, moinho, torre de vigia, aldeia 3D
        add('castle', CASTLE[0], CASTLE[2], 8.0, ry=180, col=8.0)
        add('mill', -28, 34, 6.0, ry=30, col=4.5)
        self.mill_pos = (-28.0, 34.0)
        add('watchtower', 36, 40, 5.0, ry=-40, col=3.0)
        add('house', -14, 14, 4.0, ry=20, col=3.2)
        add('house', -21, 22, 4.0, ry=-15, col=3.2)
        add('well', -16, 6, 2.6, col=1.4)
        # reinos achatados: imagens 2D no chão + construções esmagadas + escombros
        self.kingdoms = []
        for k in KINGDOMS:
            img = self.kingdom_image(k['kind'])
            tex = surf_to_rgba(img)
            w = k['w']
            h = w * img.get_height() / img.get_width() * STRETCH
            x, z = k['c']
            origin = (x - w / 2, 0.06, z - h / 2)
            self.kingdoms.append({'name': k['name'], 'tex': tex, 'o': origin, 'w': w, 'h': h, 'c': (x, z)})
        add('house', -40, -17, 4.0, ry=40, sy=0.07)          # casas esmagadas (escala Y ~ 0)
        add('house', -14, -18, 4.0, ry=-25, sy=0.06)
        add('rocks', -36, -19, 2.5, ry=70)
        add('castle', 28, 66, 6.5, ry=10, sy=0.08)          # o castelo achatado
        add('watchtower', -2, 66, 4.0, ry=80, sy=0.06)
        add('rocks', 22, 46, 2.8, ry=10)
        add('rocks', 39, -25, 2.0, ry=200)
        # árvores
        self.trees = []
        tries = 0
        while len(self.trees) < 22 and tries < 2000:
            tries += 1
            x, z = rnd.uniform(-44, 44), rnd.uniform(-36, 58)
            if self.blocked_for_tree(x, z):
                continue
            self.trees.append((x, z))
            add(rnd.choice(['treeA', 'treeB', 'treeC']), x, z, rnd.uniform(6.0, 8.5), ry=rnd.uniform(0, 360), col=0.8)
        # montanhas no horizonte
        for i in range(7):
            a = 2 * math.pi * (i + 0.3) / 7
            add('mountain', 105 * math.cos(a), 12 + 105 * math.sin(a), rnd.uniform(28, 38), ry=rnd.uniform(0, 360))
        self.build_chunks()
        # pessoas 2D andando nos reinos achatados
        self.people = []
        for ki, kg in enumerate(self.kingdoms):
            for j in range(4 if ki < 2 else 2):
                spr = rnd.choice(PEOPLE)
                img = self.assets.sprite(spr, 1)
                tex = surf_to_rgba(img)
                self.people.append({'k': ki, 'u': rnd.uniform(0.1, 0.9), 'dir': rnd.choice((-1, 1)),
                                    'speed': rnd.uniform(0.025, 0.05), 'tex': tex, 'tex_f': tex[::-1].copy(),
                                    'ph': rnd.uniform(0, 6), 'spr': spr, 'wait': 0.0})
        # nuvens
        self.clouds = []
        for i in range(9):
            a = 2 * math.pi * i / 9 + rnd.uniform(-0.2, 0.2)
            self.clouds.append((np.array([200 * math.cos(a), rnd.uniform(55, 85), 12 + 200 * math.sin(a)]),
                                rnd.uniform(35, 60), rnd.randint(0, 10 ** 6)))
        self._cloud_cache = {}
        # personagens 3D
        self.wiz = self.recolor_wizard(L('volumar'))
        self.vorax = L('vorax')
        # a textura original é bem escura: clareamos para destacar contra o céu
        self.vorax_cols = [tuple(min(255, int(c * 1.7 + 12)) for c in col) for col in self.vorax.cols]
        v = self.vorax.verts
        self.vorax_tail = np.clip((-v[:, 2] - 0.05) / 0.5, 0, 1)        # peso da deformação da cauda
        self.vorax_back = np.clip((v[:, 1] - 0.45) / 0.25, 0, 1) * np.clip(np.abs(v[:, 0]) / 0.15, 0, 1)
        self.hat = cg.cone(0.42, 0.9, 10)
        self.brim = cg.cylinder(0.68, 0.06, 12)
        self.blades = L('mill_blades')
        self.octa = cg.octahedron(0.8)

    def build_chunks(self):
        """Agrupamento de geometria estática: os objetos parados são transformados
        para o SRU uma única vez e fundidos em blocos espaciais (grade de 24 x 24),
        cada um com versão detalhada e simplificada (LOD). Menos chamadas = mais FPS."""
        mountain = MDL.load('mountain')
        groups = {}
        for m, M, (x, z), cull in self.props:
            key = 'far' if m is mountain else (math.floor(x / 24), math.floor(z / 24))
            groups.setdefault(key, []).append((m, M, x, z))

        def merge(items, low):
            vs, fs, cs, off = [], [], [], 0
            for m, M, _, _ in items:
                mm = (m.lod or m) if low else m
                vs.append(mm.verts @ M[:3, :3].T + M[:3, 3])
                fs.extend(tuple(i + off for i in f) for f in mm.faces)
                cs.extend(mm.cols)
                off += len(mm.verts)
            return np.vstack(vs), fs, cs
        self.chunks = []
        for key, items in groups.items():
            xs = [it[2] for it in items]
            zs = [it[3] for it in items]
            c = (sum(xs) / len(xs), sum(zs) / len(zs))
            rad = max(math.hypot(x - c[0], z - c[1]) for x, z in zip(xs, zs))
            lo = merge(items, True)
            self.chunks.append({'c': c, 'r': rad, 'far': key == 'far',
                                'hi': lo if key == 'far' else merge(items, False), 'lo': lo})

    def blocked_for_tree(self, x, z):
        if abs(x) < 4.5 and -26 < z < 24:
            return True
        if math.hypot(x - CASTLE[0], z - CASTLE[2]) < 13:
            return True
        cx, cz, ax, az = LAKE
        if ((x - cx) / (ax + 3)) ** 2 + ((z - cz) / (az + 3)) ** 2 < 1:
            return True
        for k in KINGDOMS:
            kx, kz = k['c']
            if abs(x - kx) < k['w'] / 2 + 3 and abs(z - kz) < k['w'] * 0.5 + 4:
                return True
        for (px, pz) in [(-28, 34), (36, 40), (-14, 14), (-21, 22), (-16, 6), (4, -22), (0, -30)]:
            if math.hypot(x - px, z - pz) < 7:
                return True
        return any(math.hypot(x - tx, z - tz) < 5 for tx, tz in getattr(self, 'trees', []))

    def recolor_wizard(self, m):
        """Tinge o manto azul de roxo para combinar com o Volumar 2D."""
        def tint(c):
            r, g, b = c
            if b > r + 10 and b > g:
                return (int(b * 0.85 + 30), int(g * 0.45), int(b * 1.05 + 20) if b < 220 else 255)
            return c
        lod = MDL.Model(m.lod.verts, m.lod.faces, [tint(c) for c in m.lod.cols]) if m.lod else None
        return MDL.Model(m.verts, m.faces, [tint(c) for c in m.cols], lod)

    def kingdom_image(self, kind):
        """Monta (com os tiles 2D coloridos) a imagem do reino que foi achatado."""
        A = self.assets
        if kind == 'village':
            s = pygame.Surface((288, 96), pygame.SRCALPHA)
            for x in range(96, 208, 16):
                s.blit(A.sprite('path', 1), (x, 64))
            scenery.house(s, A, 16, 80, 'red', 3, 1)
            scenery.house(s, A, 112, 80, 'blue', 3, 1)
            scenery.house(s, A, 208, 80, 'red', 2, 1)
            for x, kname in [(8, 'tree'), (88, 'tree_pine'), (180, 'tree_autumn'), (260, 'tree'), (276, 'bush')]:
                scenery.tree(s, A, x, 80, kname, 1)
            s.blit(A.sprite('well', 1), (164, 64))
        elif kind == 'castle':
            s = pygame.Surface((320, 112), pygame.SRCALPHA)
            scenery.castle(s, A, 96, 96, w=8, h=4, scale=1)
            for x in (40, 72, 248, 280):
                scenery.tree(s, A, x, 96, 'tree_pine', 1)
            s.blit(A.sprite('shield_crest', 1), (152, 40))
        else:
            s = pygame.Surface((192, 64), pygame.SRCALPHA)
            scenery.house(s, A, 24, 48, 'red', 2, 1)
            for x in range(80, 176, 16):
                s.blit(A.sprite('fence', 1), (x, 32))
            for x, kname in [(10, 'tree'), (96, 'mushroom'), (128, 'bush'), (180, 'tree_autumn')]:
                scenery.tree(s, A, x, 48, kname, 1)
        return s

    def cloud_img(self, px, flip, seed=0):
        key = (int(px) // 8 * 8, seed)
        if key not in self._cloud_cache:
            if len(self._cloud_cache) > 60:
                self._cloud_cache.clear()
            w = max(8, key[0])
            s = pygame.Surface((w, w // 2), pygame.SRCALPHA)
            rr = random.Random(seed)
            for _ in range(9):
                cx = rr.uniform(0.2, 0.8) * w
                cy = rr.uniform(0.45, 0.7) * w / 2
                rad = rr.uniform(0.12, 0.22) * w
                pygame.draw.circle(s, (255, 255, 255, 120), (cx, cy), rad)
            self._cloud_cache[key] = s
        return self._cloud_cache[key]

    # --------------------------------------------------------------- câmera
    def forward(self):
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        return np.array([math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)])

    def on_event(self, e):
        if e.type == pygame.MOUSEWHEEL:
            self.r.set_fov(max(25, min(100, self.r.fov - e.y * 5)))
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_c:
            self.show_cam = not self.show_cam
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_m:
            self.mouse_lock = not self.mouse_lock
            audio.sfx('ui_toggle')
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not self.mouse_lock and not self.game.driver:
            self.mouse_lock = True                     # clicar recaptura o mouse
        elif (e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE) or \
                (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
            self.shoot()
        elif e.type == pygame.MOUSEMOTION and (self._grabbed or e.buttons[2]):
            if self._skip_motion > 0:                  # ignora o "salto" logo após capturar
                self._skip_motion -= 1
                return
            k = 0.15 if self._grabbed else 0.25
            self.yaw -= e.rel[0] * k
            self.pitch = max(-60, min(70, self.pitch - e.rel[1] * k))

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
        self.update_people(dt)
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
                for ax in (0, 2):
                    cand = self.pos.copy()
                    cand[ax] = new[ax]
                    if not self.collide(cand):
                        self.pos = cand
                        break
        self.pos[1] = EYE_H + 0.06 * math.sin(t * 9) * (np.linalg.norm(mv) > 0)
        # primeira visão de um reino achatado
        if not self.seen_flat and self.state == 'explore':
            for kg in self.kingdoms[:2]:
                if math.hypot(self.pos[0] - kg['c'][0], self.pos[2] - kg['c'][1]) < 16:
                    self.seen_flat = True
                    self.say([('Sir Lineu', 'knight', 'São... planicianos! Daqui de cima eles parecem desenhos no chão, '
                                                      'andando para lá e para cá sem saber que existe um "cima".'),
                              ('Volumar', 'wizard', 'É assim que eu via você, Lineu. Vorax esmagou estes reinos e esmagaria '
                                                    'o meu também. Quando ele cair, eles recuperarão a profundidade.')])
                    break
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
                if np.linalg.norm(b['p'] - self.dragon['p']) < 4.6:
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
            if self.dragon_dead > 4.0:
                self.dragon_dead = 0
                self.complete()

    def update_people(self, dt):
        for p in self.people:
            if p['wait'] > 0:
                p['wait'] -= dt
                continue
            p['u'] += p['dir'] * p['speed'] * dt
            if p['u'] < 0.05 or p['u'] > 0.95:
                p['dir'] *= -1
                p['u'] = min(0.95, max(0.05, p['u']))
                p['wait'] = random.uniform(0.5, 2.0)
            elif random.random() < 0.003:
                p['wait'] = random.uniform(0.5, 1.5)

    def collide(self, p):
        for x, z, r in self.colliders:
            if math.hypot(p[0] - x, p[2] - z) < r:
                return True
        cx, cz, ax, az = LAKE
        if ((p[0] - cx) / ax) ** 2 + ((p[2] - cz) / az) ** 2 < 1:
            return True
        return False

    def spawn_dragon(self):
        self.dragon = {'a': 0.0, 'p': CASTLE + np.array([0, 12, -20.0]), 'hp': 10, 'max': 10, 'fire_t': 3.0,
                       'flash': 0, 'yaw': 0.0, 'bank': 0.0}

    def update_dragon(self, dt, paused):
        d = self.dragon
        if self.state == 'won':
            return
        if paused:
            dt = dt * 0.3
        d['a'] += dt * 0.35
        R = 22
        old = d['p'].copy()
        d['p'] = CASTLE + np.array([R * math.sin(d['a']), 12 + 2.5 * math.sin(d['a'] * 3), -R * math.cos(d['a']) * 0.8])
        vel = (d['p'] - old) / max(dt, 1e-6)
        d['vel'] = vel
        if np.linalg.norm(vel[[0, 2]]) > 1e-3:
            ny = math.degrees(math.atan2(vel[0], vel[2]))
            turn = nang(ny - d['yaw'])
            d['yaw'] += turn
            d['bank'] = max(-35, min(35, d['bank'] * 0.9 + turn / max(dt, 1e-3) * 0.15 * 0.1))
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
            fwd = np.array([math.sin(math.radians(d['yaw'])), 0, math.cos(math.radians(d['yaw']))])
            mouth = d['p'] + fwd * 4.5 + np.array([0, 1.2, 0])
            target = self.pos + np.array([0, -0.4, 0])
            v = cg.normalize(target - mouth) * 15
            self.fires.append({'p': mouth, 'v': v, 't': 5})
            audio.sfx('fireball', near)
            if random.random() < 0.35:
                audio.sfx('growl', near)

    # --------------------------------------------------------------- desenho
    def draw_sky(self, surf):
        top, bot = (62, 112, 196), self.r.fog_color
        horizon = VIEW.y + VIEW.h / 2 - math.tan(math.radians(self.pitch)) * (VIEW.h / 2) / math.tan(math.radians(self.r.fov / 2))
        for i in range(0, VIEW.h, 4):
            y = VIEW.y + i
            tt = max(0.0, min(1.0, 1 - (horizon - y) / (VIEW.h * 0.9)))
            c = tuple(int(top[k] + (bot[k] - top[k]) * tt ** 1.6) for k in range(3))
            pygame.draw.rect(surf, c, (0, y, W, 4))
        # sol na direção da luz
        sun = self.pos + self.r.light * 300
        p = np.append(sun, 1) @ self.r.V.T
        if p[2] < 0:
            sp = self.r._to_screen(p[None, :3])[0]
            if VIEW.inflate(200, 200).collidepoint(sp):
                for rad, a in ((90, 30), (55, 60), (32, 255)):
                    g = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
                    pygame.draw.circle(g, (255, 244, 200, a), (rad, rad), rad)
                    surf.blit(g, (sp[0] - rad, sp[1] - rad))

    def wizard_matrix(self):
        bob = 0.25 + 0.15 * math.sin(self.t * 2)
        d = self.pos - VOLUMAR_POS
        yaw = math.degrees(math.atan2(d[0], d[2]))
        return cg.T3(VOLUMAR_POS[0], bob, VOLUMAR_POS[2]) @ cg.Ry(yaw) @ cg.S3(1.15, 1.15, 1.15)

    def dragon_matrix(self, d):
        p = d['p'].copy()
        sy = 1.0
        roll = d['bank']
        if self.dragon_dead:
            k = min(1.0, self.dragon_dead / 1.6)
            p[1] = max(0.0, p[1] * (1 - k))
            roll = d['bank'] + 120 * k
            if self.dragon_dead > 1.6:            # o Achatador... achatado!
                sy = max(0.04, 1 - (self.dragon_dead - 1.6) * 1.5)
                roll = 0
                p[1] = 0.05
        return (cg.T3(*p) @ cg.Ry(d['yaw']) @ cg.Rz(roll) @ cg.S3(DRAGON_SCALE, DRAGON_SCALE * sy, DRAGON_SCALE)
                @ cg.T3(0, -0.36 if sy == 1.0 else 0.0, 0))

    def sync_mouse(self):
        """Captura o mouse durante o jogo e o libera em diálogos, no pergaminho e no fim."""
        want = (self.mouse_lock and not self.game.driver and not self.show_help and not self.completed
                and not (self.dialog and self.dialog.active) and self.game._fade_dir == 0)
        if want != self._grabbed:
            self._grabbed = want
            pygame.event.set_grab(want)
            pygame.mouse.set_visible(not want)
            pygame.mouse.get_rel()
            self._skip_motion = 2 if want else 0

    def on_draw(self, surf):
        self.sync_mouse()
        self.draw_sky(surf)
        f = self.forward()
        eye = self.pos
        r = self.r
        r.set_camera(eye, eye + f, (0, 1, 0))
        r.begin()
        for pos, size, seed in self.clouds:
            # as nuvens acompanham o jogador (ficam sempre "no céu", muito longe)
            r.billboard(pos + np.array([eye[0], 0, eye[2]]),
                        lambda px, fl, sd=seed: self.cloud_img(px, fl, sd), size, layer=-1)
        r.mesh(self.far_ground[0], self.far_ground[1], np.eye(4), (78, 140, 66), layer=-0.8, light=False)
        gv, gf, gc = self.ground
        r.mesh(gv, gf, np.eye(4), (80, 150, 70), layer=0, colors=gc)
        # lago: margem + água com brilho animado
        r.mesh(self.shore_v, self.lake_faces, np.eye(4), (214, 196, 140), layer=0.3, light=False)
        wc = [(int(64 + 14 * math.sin(self.t * 1.7 + i * 0.9)), int(128 + 16 * math.sin(self.t * 1.3 + i * 0.7)),
               int(196 + 12 * math.sin(self.t * 2.1 + i * 0.5))) for i in range(len(self.lake_faces))]
        r.mesh(self.lake_v, self.lake_faces, np.eye(4), (60, 120, 190), layer=0.4, light=False, colors=wc)
        r.mesh(self.path[0], self.path[1], self.path[2], (176, 160, 128), layer=0.45)
        # reinos achatados (textura no chão) e seus habitantes 2D
        for kg in self.kingdoms:
            if np.linalg.norm(np.array(kg['c']) - eye[[0, 2]]) < 110:
                r.decal(kg['o'], (kg['w'], 0, 0), (0, 0, kg['h']), kg['tex'], layer=0.5)
        for p in self.people:
            kg = self.kingdoms[p['k']]
            cu = kg['w'] / (kg['tex'].shape[0] / 16)          # tamanho de um tile 16px no chão
            cv = kg['h'] / (kg['tex'].shape[1] / 16)
            hop = abs(math.sin(self.t * 6 + p['ph'])) * cv * 0.25 if p['wait'] <= 0 else 0
            ox = kg['o'][0] + p['u'] * kg['w'] - cu / 2
            oz = kg['o'][2] + cv + hop
            if math.hypot(ox - eye[0], oz - eye[2]) < 70:
                tex = p['tex'] if p['dir'] > 0 else p['tex_f']
                r.decal((ox, 0.08, oz), (cu, 0, 0), (0, 0, cv), tex, layer=0.55)
        # objetos 3D estáticos, em blocos com nível de detalhe pela distância
        I4 = np.eye(4)
        for ch in self.chunks:
            dist = math.hypot(ch['c'][0] - eye[0], ch['c'][1] - eye[2]) - ch['r'] * 0.6
            v, fs, cs = ch['hi'] if (not ch['far'] and dist < 24) else ch['lo']
            r.mesh(v, fs, I4, (200, 200, 200), colors=cs, cull=True)
        # pás do moinho girando
        mx, mz = self.mill_pos
        Mb = (cg.T3(mx, 0, mz) @ cg.Ry(30) @ cg.T3(0, 6.6, -3.6) @ cg.Rz(self.t * 40) @ cg.S3(6, 6, 6)
              @ cg.T3(0, -0.69, 0))
        bl = self.blades.pick(math.hypot(mx - eye[0], mz - eye[2]), 26)
        r.mesh(bl.verts, bl.faces, Mb, (200, 200, 200), colors=bl.cols, cull=False)
        # cristais girando
        for i, c in enumerate(self.crystals):
            if not self.got[i]:
                M = cg.T3(c[0], c[1] + 0.4 * math.sin(self.t * 2 + i), c[2]) @ cg.Ry(self.t * 90)
                r.mesh(self.octa[0], self.octa[1], M, (120, 220, 255), light=True)
                r.sphere(c, 0.25, (180, 240, 255))
        # Volumar 3D (com chapéu de mago) e faíscas mágicas
        Mw = self.wizard_matrix()
        wz = self.wiz.pick(float(np.linalg.norm(VOLUMAR_POS - eye)), 30)
        r.mesh(wz.verts, wz.faces, Mw, (200, 200, 200), colors=wz.cols, cull=True)
        r.mesh(self.brim[0], self.brim[1], Mw @ cg.T3(0, 2.12, 0), (92, 44, 140))
        r.mesh(self.hat[0], self.hat[1], Mw @ cg.T3(0, 2.15, 0) @ cg.Rx(-12), (120, 60, 180))
        for k in range(3):
            a = self.t * 2 + k * 2.09
            sp = VOLUMAR_POS + np.array([1.1 * math.cos(a), 1.6 + 0.4 * math.sin(self.t * 3 + k), 1.1 * math.sin(a)])
            r.sphere(sp, 0.09, (200, 140, 255))
        # Vorax 3D: deformação de vértices (cauda ondulando) a cada quadro
        if self.dragon is not None:
            d = self.dragon
            v = self.vorax.verts.copy()
            ph = self.t * 3.0
            v[:, 0] += np.sin(ph + v[:, 2] * 7.0) * 0.07 * self.vorax_tail
            v[:, 1] += np.sin(self.t * 7.0) * 0.035 * self.vorax_back
            Md = self.dragon_matrix(d)
            cols = self.vorax_cols
            if d['flash'] > 0:
                cols = [(min(255, c[0] + 120), min(255, c[1] + 60), min(255, c[2] + 60)) for c in cols]
            r.mesh(v, self.vorax.faces, Md, (90, 60, 50), colors=cols, cull=True)
            sh = cg.box(6, 0.02, 3.2)
            r.mesh(sh[0], sh[1], cg.T3(d['p'][0], 0.07, d['p'][2]) @ cg.Ry(d['yaw'] + 90), (52, 92, 46),
                   layer=0.6, light=False)
        for b in self.bolts:
            r.sphere(b['p'], 0.22, (140, 220, 255))
        for fb in self.fires:
            r.sphere(fb['p'], 0.6, (255, 120, 30))
        r.render(surf)
        self.draw_labels(surf)
        if self.dragon is not None and self.dragon['flash'] > 0:
            fl = pygame.Surface(VIEW.size, pygame.SRCALPHA)
            fl.fill((255, 255, 255, 30))
            surf.blit(fl, VIEW.topleft)
        self.draw_hud(surf)

    def draw_labels(self, surf):
        """Nomes dos reinos achatados flutuando sobre eles (projeção de um ponto 3D)."""
        for kg in self.kingdoms:
            x, z = kg['c']
            dist = math.hypot(x - self.pos[0], z - self.pos[2])
            if dist > 34:
                continue
            p = np.append(np.array([x, 3.0, z]), 1) @ self.r.V.T
            if p[2] > -1:
                continue
            s = self.r._to_screen(p[None, :3])[0]
            if VIEW.collidepoint(s):
                text(surf, kg['name'], (s[0], s[1]), 18, (255, 240, 200), center=True)

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
        if not self.game.driver:
            tip = 'Mouse: olhar   W/A/S/D: andar   Clique/ESPAÇO: raio   M: soltar mouse' if self._grabbed else \
                'Mouse solto - clique na tela ou aperte M para controlar a câmera com o mouse'
            text(surf, tip, (W - 14, H - 26), 15, C['parch'], kind='mono', right=True)
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
            p = cg.sru_to_srd(x, z, win, vp)
            return (int(p[0]), int(p[1]))
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(vp))
        cx, cz, ax, az = LAKE
        p0, p1 = m(cx + ax, cz + az), m(cx - ax, cz - az)
        pygame.draw.ellipse(surf, (70, 130, 200), pygame.Rect(min(p0[0], p1[0]), min(p0[1], p1[1]),
                                                              abs(p1[0] - p0[0]), abs(p1[1] - p0[1])))
        for kg in self.kingdoms:
            a, b = m(kg['o'][0] + kg['w'], kg['o'][2] + kg['h']), m(kg['o'][0], kg['o'][2])
            pygame.draw.rect(surf, (200, 170, 110), pygame.Rect(a, (b[0] - a[0], b[1] - a[1])), 1)
        cr = pygame.Rect(0, 0, 22, 22)
        cr.center = m(CASTLE[0], CASTLE[2])
        pygame.draw.rect(surf, (150, 146, 140), cr)
        for x, z in self.trees:
            pygame.draw.circle(surf, (50, 130, 60), m(x, z), 2)
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
        surf.set_clip(clip)


def nang(a):
    return (a + 180) % 360 - 180
