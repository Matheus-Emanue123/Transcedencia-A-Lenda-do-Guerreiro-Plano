"""Menu principal: título, seleção de fases, configurações e créditos."""
import math
import numpy as np
import pygame

from engine.core import Scene, W, H
from engine.assets import text, text_block
from engine.ui import C, Button, panel
from engine import cg, audio

NOMES = [
    ('I', 'O Mundo de Pixels', 'Rasterização (Bresenham, Ponto Médio)'),
    ('II', 'O Vale das Cores', 'RGB, CMYK e composição alpha'),
    ('III', 'O Véu Esmeralda', 'Chroma key'),
    ('IV', 'A Fortaleza das Matrizes', 'Transformações 2D e coord. homogêneas'),
    ('V', 'O Mapa do Cartógrafo', 'SRU, SRN e SRD (window/viewport)'),
    ('VI', 'A Torre das Curvas', 'Curvas de Bézier'),
    ('VII', 'O Limiar da Profundidade', 'Projeções geométricas'),
    ('VIII', 'A Forja da Revolução', 'Superfícies e malhas'),
    ('IX', 'Transcendência', 'Câmera virtual e pipeline 3D'),
]

CREDITOS = (
    "TRANSCENDÊNCIA - A Lenda do Cavaleiro Plano\n"
    "Trabalho final de Computação Gráfica - CEFET-MG (Prof. Dr. Raulivan Rodrigo)\n\n"
    "Programação e algoritmos: implementados do zero em Python + pygame (rasterização, "
    "cores, chroma key, matrizes homogêneas, window/viewport, Bézier, projeções, câmera "
    "lookAt, superfícies de revolução e um pipeline 3D em software).\n\n"
    "Arte (todas de licença livre):\n"
    " • Personagens, masmorra e vilarejo: Kenney - 'Tiny Dungeon', 'Tiny Town' e "
    "'Pixel Platformer' (CC0) - www.kenney.nl\n"
    " • Dragão Vorax: Cethiel - 'Dragon - Fully Animated' (CC0) - OpenGameArt.org\n"
    " • Músicas (CC0, OpenGameArt.org): RandomMind ('Kings Feast', 'The Bard's Tale', 'The Old Tower Inn', "
    "'Medieval Exploration', 'Market Day', 'Rejoicing'), cesisco ('Fantasy Choir'), legoluft ('Atmospheric Puzzles') "
    "e cynicmusic ('Dramatic Boss Encounter').\n"
    " • Efeitos sonoros (CC0): Kenney (RPG Audio, Impact, Interface, UI Audio, Music Jingles, Digital Audio, "
    "Sci-fi Sounds) e OpenGameArt: rubberduck, Julien Matthey, AntumDeluge, Almitory, Ogrebane, IgnasD, "
    "themightyglider, VishwaJai, StarNinjas, Darsycho, Thimras, isaiah658, JaggedStone, SketchMan3, pyranostudios.\n"
    " • Vorax 3D: MattBas - 'Simple 3D Dragon Model' (CC-BY-SA 4.0, OpenGameArt.org), recolorido e com animações novas.\n"
    " • Modelos 3D (CC0): Volumar - Quaternius (RPG Characters); "
    "castelo, moinho, casas e montanhas - Kay Lousberg (KayKit Medieval Builder Pack); árvores e arbustos - "
    "Quaternius (via Poly Pizza).\n"
    " • Fontes: MedievalSharp (Wojciech Kalinowski) e Press Start 2P (CodeMan38) - SIL Open Font License\n"
)


class Menu(Scene):
    def __init__(self, game):
        super().__init__(game)
        audio.music('menu')
        audio.ambience([])
        audio.get().stop_loop()
        self.t = 0
        self.mode = 'main'
        bx = W // 2 - 160
        labels = [('Iniciar Jornada', self.novo), ('Continuar', self.continuar),
                  ('Selecionar Fase', lambda: self.set_mode('select')),
                  ('Configurações', lambda: self.set_mode('settings')),
                  ('Créditos', lambda: self.set_mode('credits')), ('Sair', self.sair)]
        self.buttons = [Button((bx, 290 + i * 60, 320, 50), lab, cb) for i, (lab, cb) in enumerate(labels)]
        # painel de configurações: qualidade gráfica (dois cartões) e FPS
        self.gfx_cards = [
            ('simples', 'Simplificados', 'Malhas reduzidas, nível de detalhe baixo já de perto e bordas '
                                         'serrilhadas. Mais quadros por segundo.'),
            ('bonito', 'Bonitos', 'Malhas completas, detalhe alto até longe, luz hemisférica e bordas '
                                  'suavizadas. Exige mais do computador.'),
        ]
        self.gfx_buttons = []
        for i, (key, lab, _) in enumerate(self.gfx_cards):
            b = Button((W // 2 - 470 + i * 480, 230, 460, 230), '', (lambda k=key: self.set_gfx(k)))
            b.key = key
            self.gfx_buttons.append(b)
        self.fps_button = Button((W // 2 - 170, 500, 340, 50), '', self.toggle_fps)
        self.phase_buttons = []
        done = set(game.progress.get('done', []))
        for i, (num, nome, conc) in enumerate(NOMES):
            col, row = i % 3, i // 3
            r = (110 + col * 360, 170 + row * 150, 340, 128)
            b = Button(r, '', (lambda k=i: self.game.goto_phase(k)))
            b.info = (num, nome, conc, i in done)
            self.phase_buttons.append(b)
        self.back = Button((W // 2 - 110, H - 80, 220, 48), 'Voltar', lambda: self.set_mode('main'), hotkey=pygame.K_ESCAPE)
        self.cube_v, self.cube_e = cg.cube_edges()
        self.stars = [((i * 7919) % W, (i * 104729) % H, (i % 3) + 1) for i in range(140)]

    def set_mode(self, m):
        audio.sfx('book_open' if m == 'credits' else ('ui_back' if m == 'main' else 'page'))
        self.mode = m

    def _preview(self, surf, rect, hq):
        """Vorax girando, desenhado pelo pipeline 3D na qualidade do cartão (comparação lado a lado)."""
        if not hasattr(self, '_vorax'):
            from engine import model as MDL
            from engine.render3d import Renderer3D
            self._vorax = MDL.load_anim('vorax_anim')
            self._prev_r = {}
            self._Renderer3D = Renderer3D
        key = (hq, tuple(rect))
        if key not in self._prev_r:
            r = self._Renderer3D(rect, fov=40)
            r.light = cg.normalize((0.55, 0.62, 0.55))
            r.ambient = 0.42
            r.hq = hq
            self._prev_r[key] = r
        r = self._prev_r[key]
        a = math.radians(self.t * 40)
        r.set_camera((3.3 * math.sin(a), 1.5, 3.3 * math.cos(a)), (0, 0.55, 0))
        r.begin()
        v, faces, cols = self._vorax.pose('hi' if hq else 'lo', 'Flying', self.t)
        r.mesh(v, faces, np.eye(4), (200, 200, 200), colors=cols, cull=True)
        pygame.draw.rect(surf, (150, 176, 214), rect, border_radius=6)
        r.render(surf)
        return len(faces)

    def draw_settings(self, surf):
        text(surf, 'Configurações', (W // 2, 90), 48, C['gold'], center=True)
        text(surf, 'Qualidade gráfica', (W // 2, 170), 26, C['parch'], center=True)
        cur = self.game.settings.get('gfx', 'bonito')
        for b, (key, lab, desc) in zip(self.gfx_buttons, self.gfx_cards):
            sel = key == cur
            r = b.rect
            panel(surf, r, alpha=235, border=C['gold'] if (sel or b.hover) else None)
            pr = pygame.Rect(r.x + 14, r.y + 14, 190, r.h - 28)
            nf = self._preview(surf, pr, key == 'bonito')
            text(surf, f'{nf} faces', (pr.centerx, pr.bottom - 18), 14, (30, 30, 50), center=True, kind='mono')
            tx = pr.right + 16
            text(surf, lab, (tx, r.y + 16), 28, C['gold'] if sel else C['text'])
            text_block(surf, desc, (tx, r.y + 58, r.right - tx - 14, r.h - 100), 16, C['text'], kind='serif')
            text(surf, 'Selecionado' if sel else 'Clique para escolher', (tx, r.bottom - 34), 18,
                 C['green'] if sel else C['dim'])
        self.fps_button.label = 'Mostrar FPS: ' + ('sim' if self.game.show_fps else 'não')
        self.fps_button.draw(surf)
        text(surf, 'A qualidade vale para as cenas 3D (Fases VIII e IX e o final). F3 mostra o FPS em qualquer tela.',
             (W // 2, 580), 16, C['dim'], center=True)
        self.back.draw(surf)

    def set_gfx(self, key):
        if self.game.settings.get('gfx') != key:
            self.game.set_setting('gfx', key)
            audio.sfx('powerup' if key == 'bonito' else 'page')

    def toggle_fps(self):
        self.game.show_fps = not self.game.show_fps

    def novo(self):
        from scenes import intro
        self.game.progress['done'] = []
        self.game.goto(lambda g: intro.Intro(g))

    def continuar(self):
        done = set(self.game.progress.get('done', []))
        for i in range(len(NOMES)):
            if i not in done:
                self.game.goto_phase(i)
                return
        self.game.goto_phase(len(NOMES) - 1)

    def sair(self):
        self.game.running = False

    def handle(self, e):
        if self.mode == 'main':
            for b in self.buttons:
                b.handle(e)
        elif self.mode == 'select':
            for b in self.phase_buttons:
                b.handle(e)
            self.back.handle(e)
        elif self.mode == 'settings':
            for b in self.gfx_buttons:
                b.handle(e)
            self.fps_button.handle(e)
            self.back.handle(e)
        else:
            self.back.handle(e)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.mode = 'main'

    def update(self, dt):
        self.t += dt

    def _bg(self, surf):
        surf.fill((12, 10, 22))
        for x, y, s in self.stars:
            b = 120 + int(100 * math.sin(self.t * 2 + x))
            surf.fill((b, b, min(255, b + 30)), (x, y, s, s))
        # cubo: "morph" entre projeção ortográfica achatada (2D) e perspectiva (3D)
        k = 0.5 + 0.5 * math.sin(self.t * 0.6)
        M = cg.Ry(self.t * 30) @ cg.Rx(25 + 10 * math.sin(self.t * 0.7))
        v = cg.apply4(M, self.cube_v)
        pts = []
        for x, y, z in v:
            zz = z * k
            d = 5.0
            f = d / (d - zz)
            pts.append((W // 2 + x * 70 * f, 190 + y * 70 * f * (0.25 + 0.75 * k)))
        for a, b in self.cube_e:
            pygame.draw.line(surf, (90, 70, 160), pts[a], pts[b], 2)
        # chão de pixels
        for i in range(0, W, 16):
            hgt = 6 + int(4 * math.sin(i * 0.05 + self.t))
            pygame.draw.rect(surf, (40, 34, 60), (i, H - hgt * 4, 14, hgt * 4))

    def draw(self, surf):
        self._bg(surf)
        if self.mode == 'main':
            text(surf, 'TRANSCENDÊNCIA', (W // 2, 110), 84, C['gold'], center=True)
            text(surf, 'A Lenda do Cavaleiro Plano', (W // 2, 182), 32, C['parch'], center=True)
            knight = self.assets.sprite('knight', 6)
            wiz = self.assets.sprite('wizard', 6, flip=True)
            surf.blit(knight, (W // 2 - 340, 360 + 6 * math.sin(self.t * 3)))
            surf.blit(wiz, (W // 2 + 244, 360 + 6 * math.sin(self.t * 3 + 1)))
            drg = self.assets.dragon_img(150)
            surf.blit(drg, (W - drg.get_width() - 30, H - 190 + 8 * math.sin(self.t * 1.3)))
            for b in self.buttons:
                b.draw(surf)
            text(surf, 'Trabalho Final de Computação Gráfica - CEFET-MG', (W // 2, H - 26), 16, C['dim'], center=True)
        elif self.mode == 'select':
            text(surf, 'Selecionar Fase', (W // 2, 90), 48, C['gold'], center=True)
            for b in self.phase_buttons:
                num, nome, conc, done = b.info
                panel(surf, b.rect, alpha=230, border=C['gold'] if b.hover else (C['green'] if done else None))
                text(surf, f'Fase {num}', (b.rect.x + 18, b.rect.y + 14), 20, C['gold'])
                text(surf, nome, (b.rect.x + 18, b.rect.y + 44), 24, C['text'])
                text(surf, conc, (b.rect.x + 18, b.rect.y + 82), 16, C['dim'])
                if done:
                    text(surf, '✓', (b.rect.right - 34, b.rect.y + 12), 26, C['green'], kind='serif')
            self.back.draw(surf)
        elif self.mode == 'settings':
            self.draw_settings(surf)
        else:
            r = pygame.Rect(90, 30, W - 180, H - 110)
            panel(surf, r, alpha=245)
            text(surf, 'Créditos', (r.centerx, r.y + 34), 36, C['gold'], center=True)
            text_block(surf, CREDITOS, (r.x + 36, r.y + 66, r.w - 72, r.h - 80), 18, kind="serif", spacing=3)
            self.back.draw(surf)
