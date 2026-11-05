"""Epílogo: Planícia ganha profundidade."""
import math
import pygame

from engine.core import Scene, W, H
from engine.assets import text, text_block
from engine.ui import C, Dialog
from engine.render3d import Renderer3D
from engine import cg, audio
import numpy as np

FALAS = [
    ('Vorax', 'dragon', 'Impossível... um ser nascido numa grade de pixels... dominando a profundidade...'),
    ('Volumar', 'wizard', 'Vorax achatava mundos porque acreditava que só ele merecia ter volume. Mas a geometria '
                          'pertence a quem a estuda.'),
    ('Volumar', 'wizard', 'Com o dragão derrotado, sua magia se desfaz. Olhe, Lineu: Planícia está ganhando '
                          'profundidade de novo!'),
    ('Sir Lineu', 'knight', 'Pixels, cores, matrizes, coordenadas, curvas, projeções, superfícies, câmeras... '
                            'Cada arte acrescentou algo ao meu mundo.'),
    ('Volumar', 'wizard', 'E esse é o segredo da Computação Gráfica: transformar modelos matemáticos em imagens. '
                          'Você não apenas transcendeu, Sir Lineu - você aprendeu a CRIAR mundos.'),
    ('Sir Lineu', 'knight', 'Então que venha a quarta dimensão!'),
    ('Volumar', 'wizard', '...Essa fica para a próxima disciplina.'),
]


class Ending(Scene):
    def __init__(self, game):
        super().__init__(game)
        audio.music('ending')
        audio.ambience(['amb_field'])
        audio.get().stop_loop()
        self.t = 0
        self.dialog = Dialog(self.assets, FALAS, self.done)
        self.finished = False
        self.r = Renderer3D((0, 0, W, H), fov=55)
        self.r.fog_color = (20, 16, 40)
        self.r.fog_start, self.r.fog_end = 20, 60
        cyl = cg.cylinder(1.2, 6, 10)
        cone = cg.cone(1.6, 2.5, 10)
        self.meshes = []
        for dx in (-5, 5):
            for dz in (-5, 5):
                self.meshes.append((cyl, cg.T3(dx, 0, dz), (180, 175, 170)))
                self.meshes.append((cone, cg.T3(dx, 6, dz), (190, 60, 60)))
        self.meshes.append((cg.box(9, 4, 9), cg.T3(0, 2, 0), (160, 155, 150)))
        self.meshes.append((cg.cone(4.5, 4, 4), cg.T3(0, 4, 0) @ cg.Ry(45), (60, 70, 170)))
        self.meshes.append((cg.box(40, 0.2, 40), cg.T3(0, -0.1, 0), (60, 120, 60)))

    def done(self):
        self.finished = True
        audio.sfx('gong')
        audio.sfx('jingle_win2')
        self.game.mark_done(9)

    def handle(self, e):
        if not self.finished:
            self.dialog.handle(e)
        elif e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.game.goto_menu()

    def update(self, dt):
        self.t += dt
        self.dialog.update(dt)

    def draw(self, surf):
        # o mundo "cresce" do plano para o 3D: escala em Y animada
        k = min(1.0, self.t / 6)
        surf.fill((20, 16, 40))
        a = self.t * 0.25
        self.r.set_camera((22 * math.sin(a), 6 + 6 * k, -22 * math.cos(a)), (0, 2, 0))
        self.r.begin()
        flat = cg.S3(1, max(0.02, k), 1)
        for i, ((v, f), M, col) in enumerate(self.meshes):
            self.r.mesh(v, f, flat @ M, col, layer=0 if i == len(self.meshes) - 1 else 1)
        self.r.render(surf)
        d = self.assets.dragon_img(120).copy()
        d.set_alpha(int(255 * max(0, 1 - self.t / 8)))
        surf.blit(d, (W - 300, 120 + self.t * 10))
        if self.finished:
            s = pygame.Surface((W, H), pygame.SRCALPHA)
            s.fill((0, 0, 0, 150))
            surf.blit(s, (0, 0))
            text(surf, 'FIM', (W // 2, 200), 96, C['gold'], center=True)
            text(surf, 'Sir Lineu transcendeu para a Terceira Dimensão.', (W // 2, 300), 30, C['parch'], center=True)
            text_block(surf, 'Obrigado por jogar!  Conceitos aplicados: rasterização, modelos de cor, chroma key, '
                             'transformações homogêneas, sistemas de coordenadas, curvas de Bézier, projeções, '
                             'superfícies de revolução e câmera virtual.', (W // 2 - 420, 360, 840, 200), 20, C['text'], kind='serif')
            text(surf, 'Pressione qualquer tecla para voltar ao menu', (W // 2, H - 60), 18, C['dim'], center=True)
        else:
            self.dialog.draw(surf)
