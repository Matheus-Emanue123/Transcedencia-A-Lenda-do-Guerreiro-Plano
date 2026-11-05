"""Menu principal: título, seleção de fases e créditos."""
import math
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
        self.buttons = [
            Button((bx, 330, 320, 52), 'Iniciar Jornada', self.novo),
            Button((bx, 394, 320, 52), 'Continuar', self.continuar),
            Button((bx, 458, 320, 52), 'Selecionar Fase', lambda: self.set_mode('select')),
            Button((bx, 522, 320, 52), 'Créditos', lambda: self.set_mode('credits')),
            Button((bx, 586, 320, 52), 'Sair', self.sair),
        ]
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
        else:
            r = pygame.Rect(90, 30, W - 180, H - 110)
            panel(surf, r, alpha=245)
            text(surf, 'Créditos', (r.centerx, r.y + 34), 36, C['gold'], center=True)
            text_block(surf, CREDITOS, (r.x + 36, r.y + 66, r.w - 72, r.h - 80), 18, kind="serif", spacing=3)
            self.back.draw(surf)
