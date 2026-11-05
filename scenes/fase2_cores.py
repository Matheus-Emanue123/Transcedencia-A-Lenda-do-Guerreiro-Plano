"""
FASE II - O Vale das Cores  (RGB, CMYK e composição Alpha)

O mundo chega em tons de cinza. Cada Cristal Guardião ativado devolve parte
da saturação ao vale - literalmente uma composição alpha entre a versão em
cinza e a versão colorida do cenário.
"""
import math
import pygame

from engine.core import Phase, W, H
from engine.assets import text
from engine.ui import C, Button, Slider, panel
from engine import cg, audio, scenery

WORLD_H = 430
PANEL = pygame.Rect(16, 478, W - 32, 222)
RIVER = pygame.Rect(890, 300, 200, WORLD_H - 300)

GATES = [
    {'kind': 'rgb', 'x': 260, 'name': 'Cristal da Chama', 'target': (255, 140, 0)},
    {'kind': 'cmyk', 'x': 640, 'name': 'Estandarte Real', 'target': (51, 102, 204)},
    {'kind': 'alpha', 'x': 990, 'name': 'Ponte Espectral', 'alpha': 0.65,
     'F': (255, 250, 220), 'B': (40, 90, 170)},
]


class Fase2(Phase):
    index = 1
    music = 'fase2'
    ambience = ['amb_village', 'amb_river']
    sound_style = '8bit'
    title = 'Fase II - O Vale das Cores'
    subtitle = 'Modelos de cor'
    concept_title = 'RGB (aditivo), CMYK (subtrativo) e canal Alpha'
    concept = (
        "RGB - sistema ADITIVO (luz: monitores, projetores). O repouso é o preto; somar R, G e B no máximo "
        "estimula os três cones do olho e vemos BRANCO. Cada canal vai de 0 a 255 (8 bits).\n"
        "  Ex.: vermelho + verde = amarelo;  (255,140,0) = laranja.\n\n"
        "CMYK - sistema SUBTRATIVO (tinta: impressoras). O repouso é o papel branco; cada tinta ABSORVE uma "
        "componente da luz: Ciano absorve o vermelho, Magenta o verde, Amarelo o azul. K (preto) economiza tinta.\n"
        "  R = 255·(1-C)·(1-K)    G = 255·(1-M)·(1-K)    B = 255·(1-Y)·(1-K)\n\n"
        "ALPHA (RGBA) - um 4º canal de opacidade usado para compor imagens:\n"
        "  C = α·F + (1-α)·B      (F = frente, B = fundo, α ∈ [0,1])\n"
        "α = 1 é totalmente opaco; α = 0, invisível.\n\n"
        "Nesta fase, a própria saturação do vale é uma composição alpha entre a imagem cinza e a colorida!"
    )
    intro = [
        ('Sir Lineu', 'knight', 'Onde estou? Tudo aqui tem formas... mas são todas cinzentas.'),
        ('Volumar', 'wizard', 'Este é o Vale das Cores - ou era, antes de Vorax drenar seus canais. '
                              'Três Cristais Guardiões guardam as cores. Reative-os!'),
        ('Volumar', 'wizard', 'O primeiro é o Cristal da Chama. Ele responde à LUZ: misture Vermelho, '
                              'Verde e Azul até igualar a cor-alvo. Lembre-se: luz se SOMA.'),
    ]
    outro = [
        ('Sir Lineu', 'knight', 'As cores! Vermelho, verde, azul... e tudo que existe entre eles!'),
        ('Volumar', 'wizard', 'Agora você entende que uma cor é só um vetor de números. Mas cuidado: '
                              'há quem use isso para enganar os olhos...'),
        ('Volumar', 'wizard', 'Na Floresta adiante, o Ilusionista ergueu um véu esmeralda. Prepare-se.'),
    ]

    def setup(self):
        self.world = pygame.Surface((W, WORLD_H))
        self.build_world()
        self.gray = scenery.grayscale(self.world)
        self.sat = 0.0
        self.gi = 0
        self.kx = 80.0
        self.walk_to = GATES[0]['x'] - 90
        self.cross = 0.0
        self.make_ui()
        self.hud_hint = ''

    def build_world(self):
        s = self.world
        scenery.gradient(s, (0, 0, W, WORLD_H), (120, 180, 240), (200, 230, 250))
        pygame.draw.circle(s, (255, 220, 90), (1120, 70), 40)
        scenery.hills(s, self.assets, 170, scale=4)
        pygame.draw.rect(s, (40, 160, 90), (0, 266, W, 40))
        scenery.ground(s, self.assets, WORLD_H - 144, rows=3)
        scenery.house(s, self.assets, 40, WORLD_H - 144, 'red')
        scenery.house(s, self.assets, 420, WORLD_H - 144, 'blue', w=3)
        scenery.house(s, self.assets, 740, WORLD_H - 144, 'red', w=2)
        for x, k in [(210, 'tree'), (390, 'tree_autumn'), (560, 'tree_pine'), (850, 'tree'), (1150, 'tree_pine'),
                     (1220, 'tree_autumn'), (1260, 'tree')]:
            scenery.tree(s, self.assets, x, WORLD_H - 140, k)
        for x in range(0, W, 48):
            if not RIVER.left - 48 < x < RIVER.right:
                s.blit(self.assets.sprite('path', 3), (x, WORLD_H - 96))
        scenery.water(s, RIVER, 0, GATES[2]['B'])
        # estandarte (para o portão CMYK)
        pygame.draw.rect(s, (90, 60, 30), (GATES[1]['x'] + 50, WORLD_H - 300, 6, 160))

    # ---------------------------------------------------------------- UI
    def make_ui(self):
        g = GATES[self.gi]
        x0, y0 = PANEL.x + 30, PANEL.y + 80
        self.sliders = []
        if g['kind'] == 'rgb':
            for i, (n, col) in enumerate([('R (vermelho)', (230, 70, 60)), ('G (verde)', (90, 210, 90)), ('B (azul)', (80, 130, 240))]):
                self.sliders.append(Slider((x0, y0 + i * 50, 360, 16), n, 0, 255, 0, 5, '{:.0f}', col))
        elif g['kind'] == 'cmyk':
            for i, (n, col) in enumerate([('C (ciano)', (0, 200, 220)), ('M (magenta)', (220, 0, 160)),
                                          ('Y (amarelo)', (230, 210, 0)), ('K (preto)', (120, 120, 120))]):
                self.sliders.append(Slider((x0, y0 - 10 + i * 42, 360, 14), n, 0, 100, 0, 5, '{:.0f}%', col))
        else:
            self.sliders.append(Slider((x0, y0 + 40, 360, 18), 'Alfa (opacidade da ponte)', 0, 1, 0.0, 0.05, '{:.2f}', C['parch']))
        self.confirm = Button((PANEL.x + 450, PANEL.bottom - 40, 220, 32), 'Ativar cristal', self.check, 20,
                              hotkey=pygame.K_RETURN)

    def current(self):
        g = GATES[self.gi]
        v = [s.value for s in self.sliders]
        if g['kind'] == 'rgb':
            return tuple(int(x) for x in v)
        if g['kind'] == 'cmyk':
            return cg.cmyk_to_rgb(*(x / 100 for x in v))
        return tuple(int(x) for x in cg.alpha_blend(g['F'], g['B'], v[0]))

    def target(self):
        g = GATES[self.gi]
        if g['kind'] == 'alpha':
            return tuple(int(x) for x in cg.alpha_blend(g['F'], g['B'], g['alpha']))
        return g['target']

    def check(self):
        if self.walk_to is not None or self.gi >= len(GATES):
            return
        cur, tgt = self.current(), self.target()
        d = cg.color_dist(cur, tgt)
        if d <= 18:
            self.toast(f'{GATES[self.gi]["name"]} ativado!', C['green'])
            audio.sfx('gem')
            audio.sfx('bell', 0.7)
            audio.sfx('forcefield' if GATES[self.gi]['kind'] == 'alpha' else 'magic_chime')
            self.gi += 1
            if self.gi < len(GATES):
                self.walk_to = GATES[self.gi]['x'] - 90
                msgs = {1: [('Volumar', 'wizard', 'O Estandarte Real foi pintado com TINTA, não com luz. '
                                                  'Ajuste Ciano, Magenta, Amarelo e Preto para reproduzir o azul real.'),
                            ('Volumar', 'wizard', 'Na tinta, as cores se SUBTRAEM: cada pigmento absorve parte da luz.')],
                        2: [('Volumar', 'wizard', 'O rio só pode ser cruzado pela Ponte Espectral. Ela precisa de '
                                                  'exatamente a opacidade certa: nem fantasma demais, nem sólida demais.'),
                            ('Volumar', 'wizard', 'A cor que você vê é C = α·F + (1-α)·B. Iguale a cor-alvo.')]}
                self.say(msgs[self.gi])
                self.make_ui()
            else:
                self.walk_to = W + 60
        else:
            names = ['R', 'G', 'B']
            dicas = []
            for i in range(3):
                if cur[i] - tgt[i] > 18:
                    dicas.append(f'{names[i]} alto')
                elif tgt[i] - cur[i] > 18:
                    dicas.append(f'{names[i]} baixo')
            self.toast('A cor não confere: ' + (', '.join(dicas) if dicas else 'quase lá!'), C['red'])

    def on_event(self, e):
        if self.gi < len(GATES) and self.walk_to is None:
            for s in self.sliders:
                if s.handle(e):
                    return
            self.confirm.handle(e)

    def on_update(self, dt, paused):
        target_sat = self.gi / len(GATES)
        self.sat += (target_sat - self.sat) * min(1, dt * 1.5)
        if paused:
            return
        if self.walk_to is not None:
            d = self.walk_to - self.kx
            step = 220 * dt
            if abs(d) <= step:
                self.kx = self.walk_to
                self.walk_to = None
                if self.kx > W:
                    self.complete()
            else:
                self.kx += step * (1 if d > 0 else -1)
                if int(self.kx / 38) != int((self.kx - step * (1 if d > 0 else -1)) / 38):
                    audio.sfx('step_grass')

    # ---------------------------------------------------------------- desenho
    def on_draw(self, surf):
        surf.fill(C['bg'])
        # composição alpha entre o mundo cinza e o colorido
        surf.blit(self.gray, (0, 40))
        col = self.world.copy()
        col.set_alpha(int(255 * self.sat))
        surf.blit(col, (0, 40))
        oy = 40
        # cristais
        for i, g in enumerate(GATES):
            x = g['x']
            y = oy + WORLD_H - 200 + 6 * math.sin(self.t * 2 + i)
            if g['kind'] == 'alpha':
                continue
            done = i < self.gi
            ccol = (self.target() if i == self.gi else (g['target'] if done else (150, 150, 150)))
            if i == self.gi:
                ccol = self.current()
            pts = [(x, y - 40), (x + 22, y), (x, y + 40), (x - 22, y)]
            if done:
                glow = pygame.Surface((160, 160), pygame.SRCALPHA)
                pygame.draw.circle(glow, g['target'] + (90,), (80, 80), 70)
                surf.blit(glow, (x - 80, y - 80))
            pygame.draw.polygon(surf, ccol, pts)
            pygame.draw.polygon(surf, (255, 255, 255), pts, 2)
            if g['kind'] == 'cmyk':
                flag = pygame.Rect(x + 56, oy + WORLD_H - 300, 90, 60)
                pygame.draw.rect(surf, g['target'] if done else (ccol if i == self.gi else (140, 140, 140)), flag)
                surf.blit(self.assets.sprite('shield_crest', 2), (flag.x + 30, flag.y + 14))
        # ponte espectral sobre o rio (composição alpha real)
        g = GATES[2]
        a = g['alpha'] if self.gi > 2 else (self.sliders[0].value if self.gi == 2 else 0.0)
        bridge = pygame.Surface((RIVER.w + 40, 26), pygame.SRCALPHA)
        bridge.fill(g['F'] + (int(255 * a),))
        surf.blit(bridge, (RIVER.x - 20, oy + RIVER.y + 2))
        # cavaleiro
        k = self.assets.sprite('knight', 4)
        ky = oy + WORLD_H - 96
        surf.blit(k, k.get_rect(midbottom=(self.kx, ky + 8 + 3 * abs(math.sin(self.t * 10)) * (self.walk_to is not None))))
        w = self.assets.sprite('wizard', 3, flip=True)
        surf.blit(w, (self.kx + 40, ky - 120 + 8 * math.sin(self.t * 2)))
        self.draw_panel(surf)

    def draw_panel(self, surf):
        panel(surf, PANEL, alpha=240)
        if self.gi >= len(GATES):
            text(surf, 'Todas as cores restauradas!', PANEL.center, 34, C['green'], center=True)
            return
        g = GATES[self.gi]
        text(surf, f'{g["name"]}  ({self.gi + 1}/3)', (PANEL.x + 30, PANEL.y + 12), 24, C['gold'])
        for s in self.sliders:
            s.draw(surf)
        self.confirm.draw(surf)
        cur, tgt = self.current(), self.target()
        # amostras
        sx = PANEL.x + 450
        text(surf, 'Alvo', (sx + 50, PANEL.y + 22), 20, C['parch'], center=True)
        text(surf, 'Atual', (sx + 170, PANEL.y + 22), 20, C['parch'], center=True)
        pygame.draw.rect(surf, tgt, (sx, PANEL.y + 40, 100, 100), border_radius=6)
        pygame.draw.rect(surf, cur, (sx + 120, PANEL.y + 40, 100, 100), border_radius=6)
        for xx in (sx, sx + 120):
            pygame.draw.rect(surf, C['border'], (xx, PANEL.y + 40, 100, 100), 2, border_radius=6)
        text(surf, f'({tgt[0]},{tgt[1]},{tgt[2]})', (sx + 50, PANEL.y + 146), 15, C['gold'], kind='mono', center=True)
        text(surf, f'({cur[0]},{cur[1]},{cur[2]})', (sx + 170, PANEL.y + 146), 15, C['text'], kind='mono', center=True)
        d = cg.color_dist(cur, tgt)
        text(surf, f'distância = {d:5.1f}  (meta ≤ 18)', (sx + 110, PANEL.y + 166), 15,
             C['green'] if d <= 18 else C['dim'], kind='mono', center=True)
        # dicas por canal: compara a cor RESULTANTE com o alvo
        if g['kind'] != 'alpha':
            for i, s in enumerate(self.sliders[:3] if g['kind'] == 'rgb' else []):
                h, col = self.hint(cur[i], tgt[i])
                text(surf, h, (s.rect.right + 12, s.rect.y - 6), 18, col, kind='mono')
        else:
            s = self.sliders[0]
            h, col = self.hint(s.value, g['alpha'], 0.026, 'α')
            text(surf, h, (s.rect.x, s.rect.bottom + 16), 18, col, kind='mono')
        # fórmula + diagrama
        fx = PANEL.x + 720
        if g['kind'] == 'rgb':
            text(surf, 'Mistura ADITIVA (luz)', (fx, PANEL.y + 14), 20, C['gold'])
            self.venn_add(surf, (fx + 120, PANEL.y + 128), cur)
            text(surf, 'C = (R, G, B)', (fx + 300, PANEL.y + 60), 18, C['text'], kind='mono')
            text(surf, f'  = ({cur[0]}, {cur[1]}, {cur[2]})', (fx + 300, PANEL.y + 86), 18, C['text'], kind='mono')
            text(surf, 'R+G = amarelo', (fx + 300, PANEL.y + 124), 16, C['dim'], kind='mono')
            text(surf, 'R+B = magenta', (fx + 300, PANEL.y + 146), 16, C['dim'], kind='mono')
            text(surf, 'G+B = ciano', (fx + 300, PANEL.y + 168), 16, C['dim'], kind='mono')
        elif g['kind'] == 'cmyk':
            c, m, y, k = (s.value / 100 for s in self.sliders)
            text(surf, 'Mistura SUBTRATIVA (tinta)', (fx, PANEL.y + 14), 20, C['gold'])
            self.venn_sub(surf, (fx + 110, PANEL.y + 128), (c, m, y, k))
            tx = fx + 250
            for i, (ch, v) in enumerate([('R', c), ('G', m), ('B', y)]):
                yy = PANEL.y + 48 + i * 28
                text(surf, f'{ch}=255(1-{v:.2f})(1-{k:.2f})={cur[i]}', (tx, yy), 15, C['text'], kind='mono')
            text(surf, 'C tira R, M tira G,', (tx, PANEL.y + 140), 15, C['dim'], kind='mono')
            text(surf, 'Y tira B, K escurece.', (tx, PANEL.y + 160), 15, C['dim'], kind='mono')
            # dica ao lado de cada tinta: C controla R, M controla G, Y controla B
            for i, s in enumerate(self.sliders[:3]):
                h, col = self.hint(cur[i], tgt[i])
                if 'ok' not in h:
                    # falta luz no canal -> MENOS tinta; sobra luz -> MAIS tinta
                    h = 'menos' if cur[i] < tgt[i] else 'mais'
                text(surf, f'{"RGB"[i]} {cur[i]:3d}/{tgt[i]:3d} {h}', (s.rect.x + 120, s.rect.y - 27), 15, col, kind='mono')
        else:
            a = self.sliders[0].value
            text(surf, 'Composição Alpha', (fx, PANEL.y + 14), 20, C['gold'])
            text(surf, 'C = α·F + (1-α)·B', (fx, PANEL.y + 52), 22, C['text'], kind='mono')
            text(surf, f'F (ponte) = {g["F"]}', (fx, PANEL.y + 92), 17, C['text'], kind='mono')
            text(surf, f'B (rio)   = {g["B"]}', (fx, PANEL.y + 116), 17, C['text'], kind='mono')
            text(surf, f'C = {a:.2f}·F + {1 - a:.2f}·B = {cur}', (fx, PANEL.y + 146), 17, C['text'], kind='mono')
            text(surf, f'Alvo C       = {tgt}', (fx, PANEL.y + 172), 17, C['gold'], kind='mono')

    @staticmethod
    def hint(v, t, tol=10, name=''):
        """Dica de ajuste de um canal: ↑ aumentar, ↓ diminuir, ok = dentro da margem."""
        if abs(v - t) <= tol:
            return (f'{name} ok', C['green'])
        return (f'{name} ↑' if v < t else f'{name} ↓', C['gold'] if abs(v - t) < 4 * tol else C['red'])

    def venn_add(self, surf, center, rgb):
        s = pygame.Surface((220, 160))
        s.fill((0, 0, 0))
        cx, cy = 110, 82
        for (ox, oy), base in [((-30, -18), (rgb[0], 0, 0)), ((30, -18), (0, rgb[1], 0)), ((0, 30), (0, 0, rgb[2]))]:
            c = pygame.Surface((220, 160))
            c.fill((0, 0, 0))
            pygame.draw.circle(c, base, (cx + ox, cy + oy), 44)
            s.blit(c, (0, 0), special_flags=pygame.BLEND_ADD)
        surf.blit(s, s.get_rect(center=center))
        pygame.draw.rect(surf, C['border_dark'], s.get_rect(center=center), 2)

    def venn_sub(self, surf, center, cmyk):
        c, m, y, k = cmyk
        s = pygame.Surface((200, 160))
        s.fill((255, 255, 255))
        cx, cy = 100, 82
        for (ox, oy), base in [((-28, -16), (int(255 * (1 - c)), 255, 255)), ((28, -16), (255, int(255 * (1 - m)), 255)),
                               ((0, 28), (255, 255, int(255 * (1 - y))))]:
            layer = pygame.Surface((200, 160))
            layer.fill((255, 255, 255))
            pygame.draw.circle(layer, base, (cx + ox, cy + oy), 42)
            s.blit(layer, (0, 0), special_flags=pygame.BLEND_MULT)
        kk = int(255 * (1 - k))
        dark = pygame.Surface((200, 160))
        dark.fill((kk, kk, kk))
        s.blit(dark, (0, 0), special_flags=pygame.BLEND_MULT)
        surf.blit(s, s.get_rect(center=center))
        pygame.draw.rect(surf, C['border_dark'], s.get_rect(center=center), 2)
