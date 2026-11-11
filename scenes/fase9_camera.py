"""
FASE IX - Transcendência  (Câmera virtual e pipeline 3D completo)

Sir Lineu finalmente está no 3D, vendo o mundo pela câmera virtual
(lookAt + perspectiva). Vorax lançou um FEITIÇO DIMENSIONAL que achatou sete
reinos - vilarejos 2D deitados no chão, onde os planicianos (sprites 2D)
continuam andando - e selou a magia em três Cristais Dimensionais espalhados
pelos confins do mapa. Lineu atravessa florestas, lagos e campos para absorver
os cristais... e descobre que existe um quarto: o próprio Vorax.

Técnicas: modelos OBJ/glTF simplificados + LOD, back-face culling, algoritmo do
pintor, Lambert + névoa, mapeamento de textura com perspectiva correta (os
reinos 2D no chão), animação esquelética pré-calculada (Vorax - ver
tools/bake_gltf.py), vegetação procedural (grama e flores com balanço de
vento por deformação de vértices) e escala não uniforme animada (os reinos
achatados recuperando a altura).
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
WORLD = (-92.0, 92.0, -48.0, 136.0)      # limites do mapa: x mín, x máx, z mín, z máx
CASTLE = np.array([0.0, 0.0, 30.0])
LAKES = [(24.0, 4.0, 10.5, 7.5), (38.0, 80.0, 11.0, 7.0)]      # centro x, z e semi-eixos
ALTARS = [(-80.0, 14.0), (80.0, 70.0), (0.0, 124.0)]           # onde estão os Cristais Dimensionais
EYE_H = 1.8
VOLUMAR_POS = np.array([4.0, 0.0, -22.0])
DRAGON_SCALE = 9.0
STRETCH = 2.8          # alongamento anamórfico: o desenho no chão fica legível da altura dos olhos

# reinos achatados: nome, centro (x, z), largura, tipo da imagem e habitantes 2D
KINGDOMS = [
    {'name': 'Vila de Planícia (achatada)', 'c': (-27.0, -4.0), 'w': 22.0, 'kind': 'village',
     'folk': ['princess', 'smith', 'scout', 'knight2']},
    {'name': 'Castelo de Planícia (achatado)', 'c': (12.0, 58.0), 'w': 24.0, 'kind': 'castle',
     'folk': ['king', 'knight2', 'princess']},
    {'name': 'Fazenda Plana (achatada)', 'c': (30.0, -20.0), 'w': 15.0, 'kind': 'farm',
     'folk': ['scout', 'slime']},
    {'name': 'Burgo de Pixelburgo (achatado)', 'c': (-64.0, 36.0), 'w': 26.0, 'kind': 'burgo',
     'folk': ['illusionist', 'princess', 'smith', 'knight2']},
    {'name': 'Bosque dos Cogumelos (achatado)', 'c': (66.0, 44.0), 'w': 22.0, 'kind': 'bosque',
     'folk': ['slime', 'scout', 'slime']},
    {'name': 'Cripta de Retângula (achatada)', 'c': (-56.0, 108.0), 'w': 24.0, 'kind': 'cripta',
     'folk': ['ghost', 'bat', 'demon']},
    {'name': 'Forja de Vetória (achatada)', 'c': (56.0, 104.0), 'w': 20.0, 'kind': 'forja',
     'folk': ['smith', 'knight2', 'smith']},
]
FLOWERS = [(250, 242, 230), (250, 212, 64), (232, 72, 84), (190, 112, 232), (255, 150, 190)]


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
        "Modelos OBJ/glTF (representação por faces) simplificados (agrupamento de vértices e colapso de arestas com "
        "erro quádrico), com nível de detalhe (LOD) pela distância. Visibilidade: back-face culling + pintor. "
        "Iluminação: Lambert + névoa. A grama balança por deformação de vértices.\n"
        "Os reinos achatados são TEXTURAS 2D mapeadas no chão com perspectiva correta (um raio por pixel). "
        "Vorax é animado por ESQUELETO: cada vértice segue até 4 ossos com pesos (v' = Σ wᵢ·Gᵢ·Bᵢ⁻¹·v). As poses são "
        "pré-calculadas em quadros-chave e o jogo interpola entre eles: v(t) = (1-α)·A + α·B.\n\n"
        "Controles: W/A/S/D andam (SHIFT corre), o MOUSE gira a câmera (M solta/prende o mouse; as SETAS também giram), RODA do mouse altera o FOV "
        "(zoom), ESPAÇO ou clique esquerdo lança raios mágicos, C mostra/oculta os parâmetros da câmera."
    )
    intro = [
        ('Sir Lineu', 'knight', 'Eu... eu consigo ver PROFUNDIDADE! As coisas ficam menores ao longe... as torres '
                                'têm lados que eu nunca tinha visto!'),
        ('Volumar', 'wizard', 'Bem-vindo à Terceira Dimensão! Agora você vê o mundo por uma câmera virtual: uma posição, '
                              'um ponto para onde olhar e um vetor "para cima".'),
        ('Volumar', 'wizard', 'Olhe ao redor: aqueles desenhos no chão são reinos inteiros. Vorax os ACHATOU com um '
                              'Feitiço Dimensional e selou a magia em três Cristais Dimensionais, nos confins deste mundo.'),
        ('Volumar', 'wizard', 'Absorva os três cristais e o feitiço se desfaz. Siga os feixes de luz no horizonte ou o '
                              'mapa. W/A/S/D andam (SHIFT corre) e o mouse olha ao redor.'),
    ]
    outro = []

    def setup(self):
        self.r = Renderer3D(VIEW, fov=65, near=0.15, far=400)
        self.r.fog_color = (182, 200, 228)
        self.r.fog_start, self.r.fog_end = 45, 150
        self.r.fog_max = 0.93                  # no fim da névoa os objetos quase somem: dá para não desenhá-los
        self.r.light = cg.normalize((0.55, 0.62, 0.55))
        self.r.ambient = 0.42
        self.hq = self.game.hq                 # qualidade gráfica escolhida nas Configurações
        self.r.hq = self.hq
        self.lod_far = 46 if self.hq else 20   # distância em que os blocos trocam para a malha simplificada
        self.grass_r = 30 if self.hq else 17   # até onde a grama é desenhada
        self.veg_hi = 22 if self.hq else 10    # vegetação: malha completa até aqui...
        self.veg_lo = 36 if self.hq else 22    # ...malha simplificada até aqui, e depois vira impostor (sprite)
        self._imp, self._imp_fog, self._imp_cache = {}, {}, {}
        self._imp_pixels, self._imp_budget = 0, 3
        self.pos = np.array([0.0, EYE_H, -30.0])
        self.yaw = 0.0          # 0 = olhando para +z
        self.pitch = 4.0
        self.show_cam = True
        self.mouse_lock = True        # mouse capturado: mover o mouse gira a câmera (estilo FPS)
        self._grabbed = False
        self._skip_motion = 0
        self.build_world()
        self.crystals = [np.array([x, 2.2, z]) for x, z in ALTARS]
        self.warm_up()
        self.arena = np.array([0.0, 0.0, 30.0])     # centro da batalha: o altar do último cristal absorvido
        self.pulse = 0.0                            # tremor dos reinos quando um cristal é absorvido
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
        self.props = []          # (modelo, matriz, (x, z), cull)
        self.colliders = []      # (x, z, raio)
        self.flat = []           # construções 3D esmagadas pelo feitiço (escala Y animada)
        self.veg = []            # árvores e arbustos (malha de perto, impostor de longe)

        def add(name, x, z, s, ry=0.0, sy=None, col=0.0, cull=True, y=0.0):
            m = L(name)
            M = cg.T3(x, y, z) @ cg.Ry(ry) @ cg.S3(s, s if sy is None else sy, s)
            self.props.append((m, M, (x, z), cull))
            if col:
                self.colliders.append((x, z, col))
            return M

        def flat(name, x, z, s, ry=0.0, sy=0.07):
            self.flat.append({'m': L(name), 'x': x, 'z': z, 's': s, 'ry': ry, 'sy': sy, 'ph': rnd.uniform(0, 6)})

        # chão próximo: lajotas com variação suave de verde + chão distante gigante
        s = 12.0
        verts, faces, cols = [], [], []
        for i in range(-9, 9):
            for j in range(-5, 13):
                xa, za = i * s, j * s
                b = len(verts)
                verts += [(xa, 0, za), (xa, 0, za + s), (xa + s, 0, za + s), (xa + s, 0, za)]
                faces.append((b, b + 1, b + 2, b + 3))
                g = int(9 * math.sin(xa * 0.045 + 1.3) + 8 * math.cos(za * 0.06) + rnd.randint(-5, 5))
                cols.append((86 + g, 160 + g, 72 + g // 2))
        self.ground = (np.array(verts, dtype=float), faces, cols)
        fv = np.array([(-500, -0.05, -500), (-500, -0.05, 500), (500, -0.05, 500), (500, -0.05, -500)], dtype=float)
        self.far_ground = (fv, [(0, 1, 2, 3)])
        pv, pf = cg.box(3.6, 0.04, 44)
        self.path = (pv, pf, cg.T3(0, 0.02, 0))
        # lagos (leque de triângulos com margem de areia)
        N = 28
        self.lake_faces = [(0, 1 + (i + 1) % N, 1 + i) for i in range(N)]
        self.lakes = []
        for cx, cz, ax, az in LAKES:
            wv, sv = [(cx, 0.03, cz)], [(cx, 0.015, cz)]
            for i in range(N):
                a = 2 * math.pi * i / N
                k = 1 + 0.08 * math.sin(3 * a) + 0.05 * math.cos(5 * a)
                wv.append((cx + ax * k * math.cos(a), 0.03, cz + az * k * math.sin(a)))
                sv.append((cx + (ax + 1.4) * k * math.cos(a), 0.015, cz + (az + 1.4) * k * math.sin(a)))
            self.lakes.append((np.array(sv, dtype=float), np.array(wv, dtype=float)))
        # o reino 3D de Volumar: castelo central, moinho, torres de vigia e aldeia
        add('castle', CASTLE[0], CASTLE[2], 8.0, ry=180, col=8.0)
        add('mill', -28, 34, 6.0, ry=30, col=4.5)
        self.mill_pos = (-28.0, 34.0)
        add('watchtower', 36, 40, 5.0, ry=-40, col=3.0)
        add('watchtower', 72, -32, 5.0, ry=20, col=3.0)
        add('watchtower', -74, 86, 5.0, ry=140, col=3.0)
        add('house', -14, 14, 4.0, ry=20, col=3.2)
        add('house', -21, 22, 4.0, ry=-15, col=3.2)
        add('house', 16, 92, 4.0, ry=200, col=3.2)
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
            self.kingdoms.append({'name': k['name'], 'tex': tex, 'o': origin, 'w': w, 'h': h, 'c': (x, z),
                                  'folk': k['folk']})
        flat('house', -40, -17, 4.0, ry=40)                  # Vila de Planícia
        flat('house', -14, -18, 4.0, ry=-25, sy=0.06)
        flat('castle', 28, 72, 6.5, ry=10, sy=0.08)          # Castelo de Planícia
        flat('watchtower', -4, 72, 4.0, ry=80, sy=0.06)
        flat('house', 42, -11, 4.0, ry=-60)                  # Fazenda Plana
        flat('mill', 20, -33, 5.0, ry=15, sy=0.05)
        flat('house', -80, 50, 4.0, ry=30)                   # Burgo de Pixelburgo
        flat('house', -64, 52, 4.0, ry=-10, sy=0.06)
        flat('watchtower', -47, 24, 4.5, ry=50, sy=0.05)
        flat('oak', 54, 60, 8.0, ry=40, sy=0.04)             # Bosque dos Cogumelos: até as árvores
        flat('pine', 70, 59, 9.0, ry=10, sy=0.04)
        flat('oak_autumn', 82, 46, 8.0, ry=200, sy=0.04)
        flat('watchtower', -72, 123, 4.5, ry=10, sy=0.05)    # Cripta de Retângula
        flat('house', -40, 122, 4.0, ry=70)
        flat('house', 70, 114, 4.0, ry=-30)                  # Forja de Vetória
        flat('house', 42, 115, 4.0, ry=45, sy=0.06)
        for x, z, sc, ry in [(-36, -19, 2.5, 70), (22, 46, 2.8, 10), (39, -25, 2.0, 200), (-52, 50, 2.4, 120),
                             (60, 32, 2.2, 300), (-44, 96, 2.6, 30), (48, 92, 2.4, 160)]:
            add('rocks', x, z, sc, ry=ry)
        # altares dos cristais: círculo de pedras, uma torre esmagada e árvores amaldiçoadas
        for ax, az in ALTARS:
            for k in range(6):
                a = 2 * math.pi * k / 6 + 0.3
                add('rocks', ax + 4.4 * math.cos(a), az + 4.4 * math.sin(a), 1.7, ry=rnd.uniform(0, 360))
            flat('watchtower', ax + (9 if ax < 50 else -9), az + 6, 4.5, ry=rnd.uniform(0, 360), sy=0.06)
        self.build_vegetation(rnd, add)
        # montanhas no horizonte
        for i in range(10):
            a = 2 * math.pi * (i + 0.3) / 10
            add('mountain', 176 * math.cos(a), 44 + 176 * math.sin(a), rnd.uniform(44, 60), ry=rnd.uniform(0, 360))
        self.build_chunks()
        self.build_grass(rnd)
        # pessoas 2D andando nos reinos achatados
        self.people = []
        for ki, kg in enumerate(self.kingdoms):
            for spr in kg['folk']:
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
        self.vorax = MDL.load_anim('vorax_anim')
        self.vorax_lv = 'hi' if self.hq else 'lo'
        rest = self.vorax.pose('hi', 'Flying', 0)[0]
        self.vorax_mid = float(rest[:, 1].max()) / 2          # centro vertical (o modelo é apoiado em y = 0)
        self.vorax_snout = int(np.argmax(rest[:, 2]))          # vértice mais à frente: ponta do focinho
        # peito: vértice mais baixo da linha central, logo atrás do pescoço (onde pulsa o último cristal)
        zmax = float(rest[:, 2].max())
        chest = np.nonzero((np.abs(rest[:, 0]) < 0.03) & (rest[:, 2] > 0.05 * zmax) & (rest[:, 2] < 0.4 * zmax))[0]
        self.vorax_heart = int(chest[np.argmin(rest[chest, 1])]) if len(chest) else self.vorax_snout
        self._flash_cols = {}
        self.hat = cg.cone(0.42, 0.9, 10)
        self.brim = cg.cylinder(0.68, 0.06, 12)
        self.blades = L('mill_blades')
        self.octa = cg.octahedron(0.8)
        self.shadow_box = cg.box(8, 0.02, 5)

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
            bc = (lo[0].min(axis=0) + lo[0].max(axis=0)) / 2          # esfera envolvente do bloco
            self.chunks.append({'c': c, 'r': rad, 'far': key == 'far', 'bc': tuple(bc),
                                'br': float(np.linalg.norm(lo[0] - bc, axis=1).max()) * 1.05,
                                'hi': lo if key == 'far' else merge(items, False), 'lo': lo})

    def open_ground(self, x, z, margin=0.0):
        """Chão livre de caminho, castelo, lagos e reinos achatados (onde pode nascer grama)."""
        if abs(x) < 2.4 + margin and -23 < z < 23:
            return False
        if math.hypot(x - CASTLE[0], z - CASTLE[2]) < 9 + margin:
            return False
        for cx, cz, ax, az in LAKES:
            if ((x - cx) / (ax + 1.8 + margin)) ** 2 + ((z - cz) / (az + 1.8 + margin)) ** 2 < 1:
                return False
        for kg in self.kingdoms:
            ox, oz = kg['o'][0], kg['o'][2]
            if ox - 0.6 - margin < x < ox + kg['w'] + 0.6 + margin and oz - 0.6 - margin < z < oz + kg['h'] + 0.6 + margin:
                return False
        return True

    def free(self, x, z, margin=0.0):
        """O ponto (x, z) pode receber uma árvore, arbusto ou pedra?"""
        x0, x1, z0, z1 = WORLD
        if not (x0 + 2 < x < x1 - 2 and z0 + 2 < z < z1 - 2) or not self.open_ground(x, z, margin + 2.2):
            return False
        if math.hypot(x, z + 30) < 7 or math.hypot(x - VOLUMAR_POS[0], z - VOLUMAR_POS[2]) < 5:
            return False
        if any(math.hypot(x - ax, z - az) < 7.5 + margin for ax, az in ALTARS):
            return False
        if any(math.hypot(x - cx, z - cz) < r + 1.5 + margin for cx, cz, r in self.colliders):
            return False
        return not any(math.hypot(x - f['x'], z - f['z']) < f['s'] + margin for f in self.flat)

    def build_vegetation(self, rnd, add):
        """Florestas, árvores isoladas, arbustos e pedras, sorteados por rejeição (free)."""
        x0, x1, z0, z1 = WORLD
        forests = [(-56, -26, 15), (58, -36, 13), (-84, 70, 15), (18, 102, 14), (84, 22, 13), (-22, 62, 12),
                   (44, 24, 9), (-50, 6, 9), (84, 118, 13), (-84, 124, 11), (-8, -42, 10), (-30, 100, 10)]
        self.trees = []          # (x, z) - usado no minimapa e para manter a distância entre árvores

        def spot(margin, spread=None):
            for _ in range(60):
                if spread:
                    fx, fz, fr = spread
                    x, z = rnd.gauss(fx, fr * 0.55), rnd.gauss(fz, fr * 0.55)
                else:
                    x, z = rnd.uniform(x0, x1), rnd.uniform(z0, z1)
                if self.free(x, z, margin) and all(math.hypot(x - tx, z - tz) > 4.4 for tx, tz in self.trees):
                    return x, z
            return None

        def cursed(x, z):
            near_altar = any(math.hypot(x - ax, z - az) < 20 for ax, az in ALTARS)
            near_flat = any(math.hypot(x - f['x'], z - f['z']) < 11 for f in self.flat)
            return near_altar or (near_flat and rnd.random() < 0.6)

        for n in range(104):
            p = spot(0.6, rnd.choice(forests) if n < 74 else None)
            if p is None:
                continue
            x, z = p
            self.trees.append(p)
            if cursed(x, z):                              # a magia de Vorax adoece as árvores por perto
                kind, sc = (('cursed_tree', rnd.uniform(6.5, 8.5)) if rnd.random() < 0.65
                            else ('dead_tree', rnd.uniform(4.5, 6.5)))
            elif z > 66 or rnd.random() < 0.22:           # pinheiros dominam o norte
                kind, sc = 'pine', rnd.uniform(9.0, 13.0)
            elif rnd.random() < 0.2:
                kind, sc = 'oak_autumn', rnd.uniform(7.5, 10.0)
            else:
                kind, sc = 'oak', rnd.uniform(7.5, 10.5)
            self.plant(kind, x, z, sc, rnd.uniform(0, 360), col=0.7)
        for ax, az in ALTARS:                             # três árvores amaldiçoadas em volta de cada altar
            for k in range(3):
                a = 2 * math.pi * k / 3 + rnd.uniform(0, 1.5)
                x, z = ax + 10.5 * math.cos(a), az + 10.5 * math.sin(a)
                if x0 + 2 < x < x1 - 2 and z0 + 2 < z < z1 - 2 and \
                        all(math.hypot(x - f['x'], z - f['z']) > f['s'] for f in self.flat):
                    self.trees.append((x, z))
                    self.plant('cursed_tree', x, z, rnd.uniform(7, 9), rnd.uniform(0, 360), col=0.7)
        for n in range(70):
            p = spot(0.0, rnd.choice(forests) if n < 30 else None)
            if p:
                self.plant('bush', p[0], p[1], rnd.uniform(1.2, 2.1), rnd.uniform(0, 360))
        for n in range(22):
            p = spot(0.5)
            if p:
                add('rocks', p[0], p[1], rnd.uniform(1.5, 2.8), ry=rnd.uniform(0, 360))

    def warm_up(self):
        """Prepara, ainda no carregamento, o que seria montado no primeiro uso (impostores das árvores
        e índices de faces das malhas), para o jogo não engasgar na primeira vez que cada coisa aparece."""
        for kind in sorted({tr['kind'] for tr in self.veg}):
            for ang in range(8):
                self.impostor(kind, ang)
            m = MDL.load(kind)
            for mm in (m, m.lod):
                self.r._groups(mm.faces)
                self.r._color_array(mm.cols)
        for ch in self.chunks:
            for v, fs, cs in (ch['hi'], ch['lo']):
                self.r._groups(fs)
                self.r._color_array(cs)
        for g in self.grass:
            self.r._groups(g['f'])
            self.r._color_array(g['col'])
        for fp in self.flat:
            for mm in (fp['m'], fp['m'].lod or fp['m']):
                self.r._groups(mm.faces)
                self.r._color_array(mm.cols)

    def plant(self, kind, x, z, s, ry, col=0.0):
        m = MDL.load(kind)
        self.veg.append({'kind': kind, 'm': m, 'x': x, 'z': z, 's': s, 'ry': ry, 'rad': m.radius * s,
                         'M': cg.T3(x, 0, z) @ cg.Ry(ry) @ cg.S3(s, s, s)})
        if col:
            self.colliders.append((x, z, col))

    def impostor(self, kind, ang):
        """IMPOSTOR: de longe, a árvore vira um sprite. O modelo é desenhado UMA vez, pelo nosso próprio
        pipeline, numa imagem transparente - uma para cada um de 8 ângulos de visão - e depois basta
        colar a imagem (billboard): 1 cópia em vez de ~100 polígonos por árvore."""
        key = (kind, ang)
        if key not in self._imp:
            m = MDL.load(kind)
            ext = max(1.0, 2.1 * float(np.abs(m.verts[:, [0, 2]]).max()))     # lado do quadro (altura do modelo = 1)
            size = 160
            img = pygame.Surface((size, size), pygame.SRCALPHA)
            r = Renderer3D((0, 0, size, size), fov=30)
            r.light, r.ambient, r.hq = cg.normalize((0.45, 0.62, 0.65)), self.r.ambient, True
            r.fog_start, r.fog_end = 1e8, 2e8
            d = ext * 0.5 / math.tan(math.radians(15)) * 1.02
            r.set_camera((0, 0.5 * ext, d), (0, 0.5 * ext, 0))
            r.begin()
            r.mesh(m.verts, m.faces, cg.T3(0, (ext - 1) * 0.02, 0) @ cg.Ry(ang * 45), (200, 200, 200), colors=m.cols)
            r.render(img)
            self._imp[key] = (img, ext)
        return self._imp[key]

    def impostor_img(self, kind, ang, px, fog):
        """Imagem do impostor no tamanho da tela e já misturada com a névoa (fog = 0..6).
        Redimensionar e tingir imagens a cada quadro custa caro, então tudo fica em cache: a névoa é
        aplicada uma vez na imagem-base, e os tamanhos andam em degraus de ~12% (escala geométrica),
        para que andar ou girar a câmera quase sempre reaproveite uma imagem já pronta. No máximo
        3 imagens novas são criadas por quadro (as demais usam, por um instante, o tamanho vizinho) e,
        quando o cache enche, saem só as mais antigas - assim nenhum quadro paga a conta toda de uma vez."""
        step = int(round(math.log(max(px, 6.0)) / 0.115))
        key = (kind, ang, step, fog)
        img = self._imp_cache.get(key)
        if img is None and self._imp_budget <= 0:
            for near in (step - 1, step + 1, step - 2, step + 2):
                img = self._imp_cache.get((kind, ang, near, fog))
                if img is not None:
                    return img
        if img is None:
            self._imp_budget -= 1
            bkey = (kind, ang, fog)
            base = self._imp_fog.get(bkey)
            if base is None:
                base = self.impostor(kind, ang)[0]
                if fog:
                    k = fog / 6 * self.r.fog_max
                    base = base.copy()
                    base.fill((int(255 * (1 - k)),) * 3 + (255,), special_flags=pygame.BLEND_RGBA_MULT)
                    base.fill(tuple(int(c * k) for c in self.r.fog_color) + (0,), special_flags=pygame.BLEND_RGBA_ADD)
                self._imp_fog[bkey] = base
            size = max(6, int(round(math.exp(step * 0.115))))
            img = pygame.transform.scale(base, (size, size))
            self._imp_cache[key] = img
            self._imp_pixels += size * size
            while self._imp_pixels > 8_000_000:          # ~32 MB: descarta as mais antigas
                old = self._imp_cache.pop(next(iter(self._imp_cache)))
                self._imp_pixels -= old.get_width() * old.get_height()
        return img

    def draw_vegetation(self, r, eye, fwd, cut):
        """Três níveis de detalhe pela distância: malha completa, malha simplificada e impostor."""
        fs, fe = r.fog_start, r.fog_end
        visible = r.visible
        for tr in self.veg:
            dx, dz = tr['x'] - eye[0], tr['z'] - eye[2]
            dist = math.hypot(dx, dz)
            if dist > cut or not visible((tr['x'], tr['s'] * 0.5, tr['z']), tr['rad']):
                continue
            if dist < self.veg_lo:
                mm = tr['m'] if dist < self.veg_hi else tr['m'].lod
                r.mesh(mm.verts, mm.faces, tr['M'], (200, 200, 200), colors=mm.cols, cull=True)
            else:
                # ângulo de onde a câmera vê a árvore, descontada a rotação dela, em passos de 45°
                ang = int(round((math.degrees(math.atan2(-dx, -dz)) - tr['ry']) / 45.0)) % 8
                fog = int(round(max(0.0, min(1.0, (dist - fs) / (fe - fs))) * 6))
                ext = self.impostor(tr['kind'], ang)[1]
                r.billboard((tr['x'], tr['s'] * ext * 0.5, tr['z']),
                            lambda px, fl, k=tr['kind'], a=ang, fg=fog: self.impostor_img(k, a, px, fg),
                            tr['s'] * ext)

    def build_grass(self, rnd):
        """Grama e flores PROCEDURAIS: cada lâmina é um triângulo (base no chão, ponta no alto) e
        cada flor, uma haste com um losango no topo. O mapa é dividido em células de 16 x 16 e só
        as próximas da câmera são desenhadas. As pontas ficam marcadas para o balanço do vento."""
        G = 16.0
        tufts = 26 if self.hq else 12
        x0, x1, z0, z1 = WORLD
        self.grass = []
        for ci in range(int(math.floor(x0 / G)), int(math.ceil(x1 / G))):
            for cj in range(int(math.floor(z0 / G)), int(math.ceil(z1 / G))):
                V, F, C, tips = [], [], [], []

                def blade(x, z, h, w, col):
                    a = rnd.uniform(0, math.pi)
                    dx, dz = math.cos(a) * w, math.sin(a) * w
                    b = len(V)
                    V.extend([(x - dx, 0.0, z - dz), (x + dx, 0.0, z + dz),
                              (x + rnd.uniform(-0.12, 0.12), h, z + rnd.uniform(-0.12, 0.12))])
                    F.append((b, b + 1, b + 2))
                    C.append(col)
                    tips.append(b + 2)
                    return V[b + 2]

                patch = None
                if rnd.random() < 0.4:                    # canteiro de flores de uma ou duas cores
                    patch = (ci * G + rnd.uniform(3, 13), cj * G + rnd.uniform(3, 13), rnd.sample(FLOWERS, 2))
                for _ in range(tufts):
                    x, z = ci * G + rnd.uniform(0, G), cj * G + rnd.uniform(0, G)
                    if not self.open_ground(x, z):
                        continue
                    for _ in range(rnd.randint(2, 3)):
                        k = rnd.random()
                        col = (int(58 + 62 * k), int(124 + 66 * k), int(52 + 30 * k))
                        blade(x + rnd.uniform(-0.2, 0.2), z + rnd.uniform(-0.2, 0.2), rnd.uniform(0.3, 0.7),
                              rnd.uniform(0.06, 0.11), col)
                if patch:
                    for _ in range(9 if self.hq else 5):
                        x, z = rnd.gauss(patch[0], 1.6), rnd.gauss(patch[1], 1.6)
                        if not self.open_ground(x, z):
                            continue
                        tx, ty, tz = blade(x, z, rnd.uniform(0.4, 0.65), 0.035, (60, 128, 56))
                        b, q = len(V), 0.13
                        V.extend([(tx - q, ty, tz), (tx, ty + 0.05, tz - q), (tx + q, ty, tz), (tx, ty + 0.05, tz + q)])
                        F.append((b, b + 1, b + 2, b + 3))
                        C.append(rnd.choice(patch[2]))
                        tips.extend(range(b, b + 4))
                if V:
                    v = np.array(V, dtype=float)
                    tips = np.array(tips)
                    self.grass.append({'c': (ci * G + G / 2, cj * G + G / 2), 'v': v, 'f': F, 'col': C, 'tips': tips,
                                       'ph': v[tips, 0] * 0.7 + v[tips, 2] * 0.45})

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
        elif kind == 'burgo':                             # cidade de telhados azuis
            s = pygame.Surface((320, 96), pygame.SRCALPHA)
            for x in range(0, 320, 16):
                s.blit(A.sprite('cobble', 1), (x, 80))
            for x, w in [(8, 3), (72, 2), (128, 3), (200, 2), (256, 3)]:
                scenery.house(s, A, x, 80, 'blue', w, 1)
            s.blit(A.sprite('well', 1), (184, 64))
            s.blit(A.sprite('sign', 1), (112, 64))
            s.blit(A.sprite('sign', 1), (240, 64))
        elif kind == 'bosque':                            # bosque de cogumelos
            s = pygame.Surface((256, 80), pygame.SRCALPHA)
            for x in range(0, 256, 16):
                s.blit(A.sprite('grass_flower' if (x // 16) % 3 else 'grass', 1), (x, 64))
            for x, kname in [(14, 'tree_pine'), (44, 'tree'), (70, 'mushroom'), (96, 'tree_autumn'), (120, 'bush'),
                             (140, 'mushroom'), (166, 'tree_pine'), (196, 'tree'), (218, 'mushroom'), (242, 'tree_autumn')]:
                scenery.tree(s, A, x, 64, kname, 1)
            for x in (58, 108, 180, 230):
                scenery.tree(s, A, x, 48, 'tree' if x % 4 else 'tree_pine', 1)
        elif kind == 'cripta':                            # masmorra com túmulos
            s = pygame.Surface((288, 96), pygame.SRCALPHA)
            for x in range(48, 240, 16):
                s.blit(A.sprite('wall2', 1), (x, 16))
                s.blit(A.sprite('wall', 1), (x, 32))
                s.blit(A.sprite('wall', 1), (x, 48))
                s.blit(A.sprite('floor_dark', 1), (x, 64))
            for x in (48, 224):
                s.blit(A.sprite('pillar', 1), (x, 48))
            for x in (96, 176):
                s.blit(A.sprite('torch_wall', 1), (x, 32))
            s.blit(A.sprite('door', 1), (136, 48))
            for x in (8, 28, 248, 268, 80, 200):
                s.blit(A.sprite('tomb', 1), (x, 64))
        elif kind == 'forja':                             # oficinas de pedra, bigorna e barris
            s = pygame.Surface((256, 80), pygame.SRCALPHA)
            for x in range(0, 256, 16):
                s.blit(A.sprite('cobble', 1), (x, 64))
            for x, w in [(16, 3), (160, 4)]:
                for i in range(w):
                    s.blit(A.sprite('stone_door' if i == w // 2 else 'stone_house', 1), (x + i * 16, 48))
                    s.blit(A.sprite('roof_red', 1), (x + i * 16, 32))
                s.blit(A.sprite('roof_red_top', 1), (x + (w // 2) * 16, 16))
            s.blit(A.sprite('anvil', 1), (96, 48))
            for x in (72, 120, 136):
                s.blit(A.sprite('barrel', 1), (x, 48))
            for x in (224, 240):
                s.blit(A.sprite('fence', 1), (x, 48))
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
            new[0] = max(WORLD[0], min(WORLD[1], new[0]))
            new[2] = max(WORLD[2], min(WORLD[3], new[2]))
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
        self.pulse = max(0.0, self.pulse - dt)
        # primeira visão de um reino achatado
        if not self.seen_flat and self.state == 'explore':
            for kg in self.kingdoms:
                if math.hypot(self.pos[0] - kg['c'][0], self.pos[2] - kg['c'][1]) < 16:
                    self.seen_flat = True
                    self.say([('Sir Lineu', 'knight', 'São... planicianos! Daqui de cima eles parecem desenhos no chão, '
                                                      'andando para lá e para cá sem saber que existe um "cima".'),
                              ('Volumar', 'wizard', 'É assim que eu via você, Lineu. O feitiço de Vorax esmagou sete reinos '
                                                    'como este. Enquanto os cristais existirem, eles ficam presos ao plano.')])
                    break
        # cristais: cada um guarda um terço do feitiço
        if self.state == 'explore':
            for i, c in enumerate(self.crystals):
                if not self.got[i] and np.linalg.norm((self.pos - c)[[0, 2]]) < 2.6:
                    self.absorb(i)
                    break
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
                    self.play('Hit')
                    if self.dragon['hp'] <= 0:
                        self.play('Death', 0.9)
                        self.state = 'won'
                        self.dragon_dead = 0.01
                        audio.sfx('dragon_die')
                        audio.sfx('explosion', 0.8)
                        self.toast('O último cristal se partiu! O feitiço se desfaz!', C['gold'], 5)
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
                    self.pos = self.arena + np.array([0.0, EYE_H, 0.0])
                    self.yaw, self.pitch = 0.0, 8.0
                    self.dragon['hp'] = self.dragon['max']
                    self.play('Flying')
                    self.fires = []
                    break
        self.fires = [f for f in self.fires if f['t'] > 0 and f['p'][1] > -0.5]
        if self.dragon_dead:
            if self.dragon_dead < 1.6 <= self.dragon_dead + dt:
                audio.sfx('thud')
                audio.sfx('victory')
            self.dragon_dead += dt
            if self.dragon_dead > 5.4:              # dá tempo de ver os reinos recuperando a altura
                self.complete()

    def absorb(self, i):
        """Absorve o cristal i: os reinos tremem e tentam se erguer; o terceiro revela o último cristal."""
        self.got[i] = True
        self.pulse = 2.0
        self.arena = np.array([self.crystals[i][0], 0.0, self.crystals[i][2]])
        audio.sfx('gem2')
        audio.sfx('powerup')
        audio.sfx('thud')
        n = sum(self.got)
        self.toast(f'Cristal Dimensional {n}/3 absorvido!', C['green'])
        if n == 1:
            self.say([('Sir Lineu', 'knight', 'O cristal se desfez na minha mão... e o chão TREMEU!'),
                      ('Volumar', 'wizard', 'Você absorveu um terço do feitiço! Viu as torres esmagadas? Elas tentaram se '
                                            'erguer. Faltam dois cristais.')])
        elif n == 2:
            self.say([('Volumar', 'wizard', 'Dois terços! O feitiço está por um fio... mas sinto algo estranho, Lineu. '
                                            'A magia não está só nas pedras.')])
        else:
            self.state = 'battle'
            self.spawn_dragon()
            audio.music('boss')
            audio.sfx('roar')
            audio.sfx('wings')
            self.say([('Sir Lineu', 'knight', 'O terceiro cristal! ...Mas os reinos continuam achatados. Por quê?!'),
                      ('Volumar', 'wizard', 'Porque existe um QUARTO cristal. Vorax não guardou o coração do feitiço numa '
                                            'pedra: ele o engoliu. O último cristal é o PRÓPRIO VORAX!'),
                      ('Vorax', 'dragon', 'Tolos! Enquanto eu viver, o mundo continuará PLANO. Esmaguei seu reino até '
                                          'virar pixels... e farei o mesmo com você!'),
                      ('Volumar', 'wizard', 'Mire com a câmera, Lineu! O centro da tela é a direção de projeção. '
                                            'ESPAÇO ou clique lança os raios. Desvie das bolas de fogo andando!'),
                      ('Sir Lineu', 'knight', 'Por Planícia... e pela Terceira Dimensão!')])

    def flat_height(self):
        """(rise, shake): quanto os reinos achatados já se ergueram (0..1) e o tremor do cristal absorvido."""
        rise = 0.0
        if self.dragon_dead > 1.6:
            x = min(1.0, (self.dragon_dead - 1.6) / 2.8)
            rise = x * x * (3 - 2 * x)
        shake = math.sin(math.pi * (1 - self.pulse / 2.0)) ** 2 if self.pulse > 0 else 0.0
        return rise, shake

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
        return any(((p[0] - cx) / ax) ** 2 + ((p[2] - cz) / az) ** 2 < 1 for cx, cz, ax, az in LAKES)

    def spawn_dragon(self):
        self.dragon = {'a': 0.0, 'p': self.arena + np.array([0, 12, -20.0]), 'hp': 10, 'max': 10, 'fire_t': 3.0,
                       'flash': 0, 'yaw': 0.0, 'bank': 0.0, 'anim': 'Flying', 'at': 0.0, 'speed': 1.0}

    def play(self, anim, speed=1.0):
        """Troca a animação de Vorax (ataque e dano tocam uma vez e voltam ao voo; a morte fica no fim)."""
        d = self.dragon
        if d['anim'] == 'Death':
            return
        d['anim'], d['at'], d['speed'] = anim, 0.0, speed

    def update_dragon(self, dt, paused):
        d = self.dragon
        # relógio da animação: as que tocam uma vez só voltam ao voo quando terminam
        d['at'] += dt * d['speed'] * (0.3 if paused else 1.0)
        if d['anim'] not in ('Flying', 'Death') and d['at'] >= self.vorax.dur[d['anim']]:
            d['anim'], d['at'], d['speed'] = 'Flying', 0.0, 1.0
        if self.state == 'won':
            return
        if paused:
            dt = dt * 0.3
        d['a'] += dt * 0.35
        R = 22
        old = d['p'].copy()
        d['p'] = self.arena + np.array([R * math.sin(d['a']), 12 + 2.5 * math.sin(d['a'] * 3), -R * math.cos(d['a']) * 0.8])
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
            self.play('Attack', 1.5)
            d['spit'] = 0.55 * self.vorax.dur['Attack'] / 1.5      # cospe no meio do bote, com a boca aberta
            if random.random() < 0.35:
                audio.sfx('growl', near)
        if d.get('spit', 0) > 0:
            d['spit'] -= dt
            if d['spit'] <= 0 and d['anim'] == 'Attack':
                mouth = self.snout_world(d)
                target = self.pos + np.array([0, -0.4, 0])
                v = cg.normalize(target - mouth) * 15
                self.fires.append({'p': mouth, 'v': v, 't': 5})
                audio.sfx('fireball', near)

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

    def snout_world(self, d):
        """Ponta do focinho na pose atual, levada ao mundo pela matriz do dragão (de onde sai o fogo)."""
        v = self.vorax.pose('hi', d['anim'], d['at'])[0][self.vorax_snout]
        return (self.dragon_matrix(d) @ np.append(v, 1.0))[:3]

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
            roll = d['bank'] * (1 - k)            # a animação de morte cuida da queda do corpo
            if self.dragon_dead > 1.6:            # o Achatador... achatado!
                sy = max(0.04, 1 - (self.dragon_dead - 1.6) * 1.5)
                roll = 0
                p[1] = 0.05
        return (cg.T3(*p) @ cg.Ry(d['yaw']) @ cg.Rz(roll) @ cg.S3(DRAGON_SCALE, DRAGON_SCALE * sy, DRAGON_SCALE)
                @ cg.T3(0, -self.vorax_mid if sy == 1.0 else 0.0, 0))

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
        self._imp_budget = 3
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
        # lagos: margem + água com brilho animado
        ph = np.arange(len(self.lake_faces))
        wc = np.stack([64 + 14 * np.sin(self.t * 1.7 + ph * 0.9), 128 + 16 * np.sin(self.t * 1.3 + ph * 0.7),
                       196 + 12 * np.sin(self.t * 2.1 + ph * 0.5)], axis=1).astype(np.float32)
        for shore_v, lake_v in self.lakes:
            r.mesh(shore_v, self.lake_faces, np.eye(4), (214, 196, 140), layer=0.3, light=False)
            r.mesh(lake_v, self.lake_faces, np.eye(4), (60, 120, 190), layer=0.4, light=False, colors=wc)
        r.mesh(self.path[0], self.path[1], self.path[2], (176, 160, 128), layer=0.45)
        rise, shake = self.flat_height()
        cut = r.fog_end + 10                      # além disso a névoa já esconde tudo
        # reinos achatados (textura no chão) e seus habitantes 2D; somem quando o feitiço se desfaz
        if rise < 0.5:
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
            if ch['far']:                             # montanhas: menos névoa, para aparecerem no horizonte
                v, fs, cs = ch['lo']
                r.mesh(v, fs, None, (200, 200, 200), colors=cs, cull=True, fogk=0.6)
                continue
            dist = math.hypot(ch['c'][0] - eye[0], ch['c'][1] - eye[2])
            if dist - ch['r'] > cut or not r.visible(ch['bc'], ch['br']):
                continue
            v, fs, cs = ch['hi'] if dist - ch['r'] * 0.6 < self.lod_far else ch['lo']
            r.mesh(v, fs, None, (200, 200, 200), colors=cs, cull=True)
        self.draw_vegetation(r, eye, f, cut)
        # construções esmagadas pelo feitiço: escala Y não uniforme (tremem com cada cristal e
        # recuperam a altura quando o último se parte)
        for fp in self.flat:
            dist = math.hypot(fp['x'] - eye[0], fp['z'] - eye[2])
            if dist > cut or not r.visible((fp['x'], 0.0, fp['z']), fp['m'].radius * fp['s']):
                continue
            sy = fp['sy'] + (1 - fp['sy']) * rise + shake * (0.14 + 0.1 * abs(math.sin(self.t * 23 + fp['ph'])))
            M = cg.T3(fp['x'], 0, fp['z']) @ cg.Ry(fp['ry']) @ cg.S3(fp['s'], fp['s'] * min(1.0, sy), fp['s'])
            # esmagada, a construção é quase uma laje: a malha simplificada basta até ela se erguer
            mm = fp['m'].pick(dist, self.lod_far) if rise > 0 else (fp['m'].lod or fp['m'])
            r.mesh(mm.verts, mm.faces, M, (200, 200, 200), colors=mm.cols, cull=True)
        # grama e flores perto da câmera, com as pontas balançando ao vento
        gr = self.grass_r
        for g in self.grass:
            if abs(g['c'][0] - eye[0]) < gr and abs(g['c'][1] - eye[2]) < gr and \
                    r.visible((g['c'][0], 0.3, g['c'][1]), 12.5):
                v = g['v'].copy()
                sway = np.sin(self.t * 2.2 + g['ph']) * 0.07
                v[g['tips'], 0] += sway
                v[g['tips'], 2] += sway * 0.6
                r.mesh(v, g['f'], None, (90, 160, 70), colors=g['col'], cull=False, light=False)
        # pás do moinho girando
        mx, mz = self.mill_pos
        Mb = (cg.T3(mx, 0, mz) @ cg.Ry(30) @ cg.T3(0, 6.6, -3.6) @ cg.Rz(self.t * 40) @ cg.S3(6, 6, 6)
              @ cg.T3(0, -0.69, 0))
        bl = self.blades.pick(math.hypot(mx - eye[0], mz - eye[2]), self.lod_far)
        r.mesh(bl.verts, bl.faces, Mb, (200, 200, 200), colors=bl.cols, cull=False)
        # cristais girando, cada um com um feixe de luz visível de longe
        for i, c in enumerate(self.crystals):
            if not self.got[i]:
                r.line(c + np.array([0, 1.0, 0]), c + np.array([0, 80.0, 0]), (150, 235, 255), 3)
                M = cg.T3(c[0], c[1] + 0.4 * math.sin(self.t * 2 + i), c[2]) @ cg.Ry(self.t * 90)
                r.mesh(self.octa[0], self.octa[1], M @ cg.S3(1.25, 1.6, 1.25), (120, 225, 255), light=False,
                       outline=(235, 250, 255))
                r.sphere(c + np.array([0, 0.4 * math.sin(self.t * 2 + i), 0]), 0.3, (200, 245, 255), layer=1.02)
        # Volumar 3D (com chapéu de mago) e faíscas mágicas
        Mw = self.wizard_matrix()
        wz = self.wiz.pick(float(np.linalg.norm(VOLUMAR_POS - eye)), self.lod_far)
        r.mesh(wz.verts, wz.faces, Mw, (200, 200, 200), colors=wz.cols, cull=True)
        r.mesh(self.brim[0], self.brim[1], Mw @ cg.T3(0, 2.12, 0), (92, 44, 140))
        r.mesh(self.hat[0], self.hat[1], Mw @ cg.T3(0, 2.15, 0) @ cg.Rx(-12), (120, 60, 180))
        for k in range(3):
            a = self.t * 2 + k * 2.09
            sp = VOLUMAR_POS + np.array([1.1 * math.cos(a), 1.6 + 0.4 * math.sin(self.t * 3 + k), 1.1 * math.sin(a)])
            r.sphere(sp, 0.09, (200, 140, 255))
        # Vorax 3D: pose da animação esquelética, interpolada entre dois quadros-chave
        if self.dragon is not None:
            d = self.dragon
            v, faces, cols = self.vorax.pose(self.vorax_lv, d['anim'], d['at'], loop=d['anim'] != 'Death')
            Md = self.dragon_matrix(d)
            if d['flash'] > 0:
                if self.vorax_lv not in self._flash_cols:
                    self._flash_cols[self.vorax_lv] = [(min(255, c[0] + 120), min(255, c[1] + 60), min(255, c[2] + 60))
                                                       for c in cols]
                cols = self._flash_cols[self.vorax_lv]
            r.mesh(v, faces, Md, (90, 60, 50), colors=cols, cull=True)
            if self.state == 'battle':            # o último cristal pulsa no peito de Vorax
                hv = self.vorax.pose('hi', d['anim'], d['at'])[0][self.vorax_heart]
                heart = (Md @ np.append(hv, 1.0))[:3]
                r.sphere(heart, 0.5 + 0.14 * math.sin(self.t * 7), (130, 235, 255), layer=1.02)
            sh = self.shadow_box
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
        gems = [(120, 220, 255) if g else (60, 60, 80) for g in self.got]
        if self.state != 'explore':               # o quarto cristal só aparece quando é revelado
            k = 0.5 + 0.5 * math.sin(self.t * 6)
            gems.append((120, 220, 255) if self.state == 'won' else (int(150 + 100 * k), 40, int(70 + 50 * k)))
        for i, col in enumerate(gems):
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
            text(surf, 'VORAX, O ÚLTIMO CRISTAL', (W // 2, 80), 18, C['gold'], center=True)
        elif self.state == 'explore':
            text(surf, f'Absorva os Cristais Dimensionais para desfazer o feitiço ({sum(self.got)}/3) - siga os feixes de luz',
                 (W // 2, 56), 20, C['parch'], center=True)
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
        panel(surf, r, alpha=238, radius=6)
        win = (WORLD[1], WORLD[0], WORLD[2], WORLD[3])     # x invertido: visto de cima
        vp = (r.x + 8, r.y + 8, r.w - 16, r.h - 16)

        def m(x, z):
            p = cg.sru_to_srd(x, z, win, vp)
            return (int(p[0]), int(p[1]))
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(vp))
        for cx, cz, ax, az in LAKES:
            p0, p1 = m(cx + ax, cz + az), m(cx - ax, cz - az)
            pygame.draw.ellipse(surf, (70, 130, 200), pygame.Rect(min(p0[0], p1[0]), min(p0[1], p1[1]),
                                                                  abs(p1[0] - p0[0]), abs(p1[1] - p0[1])))
        for kg in self.kingdoms:
            a, b = m(kg['o'][0] + kg['w'], kg['o'][2] + kg['h']), m(kg['o'][0], kg['o'][2])
            pygame.draw.rect(surf, (200, 170, 110), pygame.Rect(a, (b[0] - a[0], b[1] - a[1])), 1)
        cr = pygame.Rect(0, 0, 14, 14)
        cr.center = m(CASTLE[0], CASTLE[2])
        pygame.draw.rect(surf, (150, 146, 140), cr)
        for x, z in self.trees:
            surf.set_at(m(x, z), (70, 150, 80))
        for i, c in enumerate(self.crystals):
            if not self.got[i]:
                pygame.draw.circle(surf, (120, 220, 255), m(c[0], c[2]), 4 + int(1.5 * math.sin(self.t * 5)))
                pygame.draw.circle(surf, (255, 255, 255), m(c[0], c[2]), 2)
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
