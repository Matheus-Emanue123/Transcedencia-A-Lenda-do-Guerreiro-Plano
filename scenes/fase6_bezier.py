"""
FASE VI - A Torre das Curvas  (Curvas de Bézier / De Casteljau)

Na torre de Volumar nada anda em linha reta. Sir Lineu arrasta os pontos de
controle para moldar a trajetória de uma bola de fogo mágica, que precisa
passar pelos anéis rúnicos sem bater nos pilares. A pré-visualização mostra
só o início da curva: é preciso entender o papel dos pontos de controle.
"""
import math
import pygame

from engine.core import Phase, W, H
from engine.assets import text
from engine.ui import C, panel, dashed_line
from engine import cg, audio

TOP = 44

LEVELS = [
    {'pts': [(130, 560), (640, 600), (1150, 560)], 'drag': [1],
     'walls': [pygame.Rect(600, 380, 70, 340)], 'rings': [(635, 300)], 'goal': 'crystal'},
    {'pts': [(130, 560), (400, 560), (900, 300), (1150, 300)], 'drag': [1, 2],
     'walls': [pygame.Rect(420, 40, 56, 360), pygame.Rect(800, 340, 56, 380)],
     'rings': [(448, 500), (828, 240)], 'goal': 'crystal'},
    {'pts': [(130, 600), (400, 600), (800, 300), (1130, 220)], 'drag': [1, 2],
     'walls': [pygame.Rect(360, 40, 50, 400), pygame.Rect(760, 330, 50, 390), pygame.Rect(1000, 330, 50, 390)],
     'rings': [(385, 520), (785, 250), (1025, 260)], 'goal': 'dragon'},
]


class Fase6(Phase):
    index = 5
    music = 'fase6'
    ambience = ['amb_wind']
    title = 'Fase VI - A Torre das Curvas'
    subtitle = 'Curvas de Bézier'
    concept_title = 'Curvas de Bézier e o algoritmo de De Casteljau'
    concept = (
        "Uma curva paramétrica é descrita por um parâmetro t ∈ [0,1] que 'caminha' pela curva.\n\n"
        "Pierre Bézier (Renault) definiu curvas por PONTOS DE CONTROLE. A curva começa em P0, termina no último ponto "
        "e é 'puxada' pelos intermediários, sem passar por eles.\n\n"
        "Quadrática:  B(t) = (1-t)²·P0 + 2(1-t)t·P1 + t²·P2\n"
        "Cúbica:      B(t) = (1-t)³·P0 + 3(1-t)²t·P1 + 3(1-t)t²·P2 + t³·P3     (base de Bernstein)\n\n"
        "Propriedades úteis:\n"
        " • a curva é TANGENTE ao segmento P0P1 no início e ao segmento P(n-1)Pn no fim;\n"
        " • a curva fica dentro do FECHO CONVEXO dos pontos de controle;\n"
        " • na quadrática, B(0.5) = P0/4 + P1/2 + P2/4.\n\n"
        "DE CASTELJAU: interpola linearmente (lerp) cada par de pontos consecutivos com o mesmo t, repetidamente, até "
        "sobrar um ponto - esse é B(t). As linhas coloridas durante o voo mostram essa construção.\n\n"
        "Arraste os pontos de controle (círculos dourados) e pressione ESPAÇO para lançar."
    )
    intro = [
        ('Volumar', 'wizard', 'Bem-vindo à minha torre! Aqui a magia não voa em linha reta: ela segue curvas '
                              'de Bézier. Vorax está escondido no topo.'),
        ('Volumar', 'wizard', 'Arraste os pontos de controle para moldar a trajetória da bola de fogo. Ela precisa '
                              'passar pelos anéis rúnicos e não pode tocar nos pilares.'),
        ('Volumar', 'wizard', 'Minha visão só alcança o começo da curva. O resto você terá de deduzir das '
                              'propriedades das curvas. ESPAÇO lança o feitiço.'),
    ]
    outro = [
        ('Vorax', 'dragon', 'GRRRAAAH! Um verme plano ousa me ferir com curvas?! Você não me alcançará no meu '
                            'domínio... a TERCEIRA DIMENSÃO!'),
        ('Volumar', 'wizard', 'Ele fugiu através do Limiar da Profundidade. Para atravessá-lo, você precisará '
                              'entender como o 3D é projetado no 2D - é assim que nós, os volumétricos, aparecemos no seu mundo.'),
    ]

    def setup(self):
        self.li = 0
        self.load()

    def load(self):
        L = LEVELS[self.li]
        self.pts = [list(p) for p in L['pts']]
        self.drag_i = None
        self.ball = None
        self.trail = []
        self.last_trail = []
        self.passed = set()
        self.boom = None
        self.won_t = 0
        self.hud_hint = 'Arraste os pontos dourados   •   ESPAÇO: lançar'

    def on_event(self, e):
        if self.ball or self.won_t:
            return
        L = LEVELS[self.li]
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i in L['drag']:
                if math.hypot(e.pos[0] - self.pts[i][0], e.pos[1] - self.pts[i][1]) < 18:
                    self.drag_i = i
                    audio.sfx('ui_pluck')
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.drag_i is not None:
                audio.sfx('ui_drop', 0.6)
            self.drag_i = None
        elif e.type == pygame.MOUSEMOTION and self.drag_i is not None:
            self.pts[self.drag_i] = [max(10, min(W - 10, e.pos[0])), max(TOP + 6, min(H - 10, e.pos[1]))]
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
            audio.sfx('cast_fire')
            audio.sfx('fireball')
            self.ball = 0.0
            self.trail = []
            self.passed = set()

    def on_update(self, dt, paused):
        if self.boom:
            self.boom[2] -= dt
            if self.boom[2] <= 0:
                self.boom = None
        if paused:
            return
        if self.won_t:
            self.won_t += dt
            if self.won_t > 1.5:
                self.won_t = 0
                self.li += 1
                if self.li >= len(LEVELS):
                    self.li = len(LEVELS) - 1
                    self.won_t = 99
                    self.complete()
                else:
                    self.load()
                    if self.li == 1:
                        self.say([('Volumar', 'wizard', 'Agora uma curva CÚBICA: dois pontos de controle. Note que a '
                                                        'curva sai na direção de P1 e chega vindo da direção de P2.')])
                    else:
                        self.say([('Vorax', 'dragon', 'Hahaha! Três anéis e três pilares! Nenhuma linha reta '
                                                      'jamais chegará até mim!'),
                                  ('Sir Lineu', 'knight', 'Ainda bem que eu não uso linhas retas.')])
            return
        audio.get().loop('amb_fire', self.ball is not None, 1.4)
        if self.ball is not None:
            self.ball += dt * 0.42
            t = min(1.0, self.ball)
            p = cg.bezier(self.pts, t)
            self.trail.append(p)
            L = LEVELS[self.li]
            for i, rg in enumerate(L['rings']):
                if math.hypot(p[0] - rg[0], p[1] - rg[1]) < 34:
                    if i not in self.passed:
                        audio.sfx('bell2')
                    self.passed.add(i)
            for wr in L['walls']:
                if wr.collidepoint(p):
                    self.fail(p, 'A bola de fogo bateu no pilar!')
                    return
            if t >= 1.0:
                if len(self.passed) == len(L['rings']):
                    self.won_t = 0.01
                    audio.sfx('glass_break' if L['goal'] == 'crystal' else 'roar')
                    audio.sfx('explosion', 0.7)
                    self.boom = [p[0], p[1], 0.8]
                    self.toast('Alvo atingido!' if L['goal'] == 'crystal' else 'Vorax foi atingido!', C['green'])
                    self.ball = None
                else:
                    self.fail(p, f'Faltaram anéis: {len(self.passed)}/{len(L["rings"])}')

    def fail(self, p, msg):
        audio.get().loop('amb_fire', False)
        audio.sfx('crunch')
        audio.sfx('stones')
        self.boom = [p[0], p[1], 0.8]
        self.last_trail = list(self.trail)
        self.ball = None
        self.toast(msg, C['red'])

    # ---------------------------------------------------------------- desenho
    def on_draw(self, surf):
        wall = self.assets.sprite('stone_wall', 3)
        for x in range(0, W, 48):
            for y in range(40, H, 48):
                surf.blit(wall, (x, y))
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((10, 0, 30, 150))
        surf.blit(shade, (0, 0))
        L = LEVELS[self.li]
        brick = self.assets.sprite('brick', 3)
        for wr in L['walls']:
            clip = surf.get_clip()
            surf.set_clip(wr)
            for x in range(wr.x, wr.right, 48):
                for y in range(wr.y, wr.bottom, 48):
                    surf.blit(brick, (x, y))
            surf.set_clip(clip)
            pygame.draw.rect(surf, (20, 10, 30), wr, 3)
        for i, rg in enumerate(L['rings']):
            col = C['green'] if i in self.passed else C['gold']
            k = 3 * math.sin(self.t * 3 + i)
            pygame.draw.circle(surf, col, rg, int(34 + k), 4)
            pygame.draw.circle(surf, col, rg, int(26 + k), 1)
        # alvo
        end = self.pts[-1]
        if L['goal'] == 'crystal':
            y = end[1] + 5 * math.sin(self.t * 2)
            pts = [(end[0], y - 30), (end[0] + 18, y), (end[0], y + 30), (end[0] - 18, y)]
            pygame.draw.polygon(surf, (120, 220, 255), pts)
            pygame.draw.polygon(surf, (255, 255, 255), pts, 2)
        else:
            d = self.assets.dragon_img(170)
            surf.blit(d, d.get_rect(midleft=(end[0] - 40, end[1] - 20 + 8 * math.sin(self.t * 1.7))))
        # mago com o cajado em P0
        p0 = self.pts[0]
        wz = self.assets.sprite('wizard', 4)
        surf.blit(wz, wz.get_rect(midright=(p0[0] - 6, p0[1] + 20)))
        kn = self.assets.sprite('knight', 4)
        surf.blit(kn, kn.get_rect(midright=(p0[0] - 70, p0[1] + 20)))
        # polígono de controle
        for i in range(len(self.pts) - 1):
            dashed_line(surf, (200, 180, 255), self.pts[i], self.pts[i + 1], 2, 10)
        # pré-visualização limitada (20% inicial) + rastro da última tentativa
        if self.last_trail and len(self.last_trail) > 1:
            pygame.draw.lines(surf, (150, 90, 90), False, self.last_trail, 2)
        pre = cg.bezier_curve(self.pts, 24, 0, 0.2)
        pygame.draw.lines(surf, (255, 200, 120), False, pre, 3)
        # voo com construção de De Casteljau
        if self.ball is not None:
            t = min(1.0, self.ball)
            levels = cg.de_casteljau(self.pts, t)
            cols = [(120, 200, 255), (120, 255, 160), (255, 220, 100)]
            for k, lv in enumerate(levels[1:-1]):
                if len(lv) > 1:
                    pygame.draw.lines(surf, cols[k % 3], False, lv, 2)
                for p in lv:
                    pygame.draw.circle(surf, cols[k % 3], (int(p[0]), int(p[1])), 4)
            if len(self.trail) > 1:
                pygame.draw.lines(surf, (255, 150, 60), False, self.trail, 4)
            p = levels[-1][0]
            glow = pygame.Surface((80, 80), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 140, 40, 90), (40, 40), 36)
            surf.blit(glow, (p[0] - 40, p[1] - 40))
            pygame.draw.circle(surf, (255, 200, 80), (int(p[0]), int(p[1])), 12)
            pygame.draw.circle(surf, (255, 255, 220), (int(p[0]), int(p[1])), 6)
        if self.boom:
            x, y, t = self.boom
            rr = int(60 * (1 - t / 0.8)) + 6
            pygame.draw.circle(surf, (255, 120, 40), (int(x), int(y)), rr, 5)
        # pontos de controle
        for i, p in enumerate(self.pts):
            drag = i in L['drag']
            col = C['gold'] if drag else (200, 200, 220)
            pygame.draw.circle(surf, (20, 10, 20), (int(p[0]), int(p[1])), 13)
            pygame.draw.circle(surf, col, (int(p[0]), int(p[1])), 11 if drag else 7)
            text(surf, f'P{i}', (p[0] + 14, p[1] - 28), 18, col)
        self.draw_panel(surf)

    def draw_panel(self, surf):
        r = pygame.Rect(W - 470, 52, 456, 168)
        panel(surf, r, alpha=225)
        L = LEVELS[self.li]
        n = len(self.pts) - 1
        text(surf, f'Feitiço {self.li + 1}/{len(LEVELS)} - Bézier de grau {n}', (r.x + 16, r.y + 10), 20, C['gold'])
        if n == 2:
            text(surf, 'B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2', (r.x + 16, r.y + 44), 16, C['text'], kind='mono')
        else:
            text(surf, 'B(t) = (1-t)³P0 + 3(1-t)²tP1', (r.x + 16, r.y + 44), 16, C['text'], kind='mono')
            text(surf, '       + 3(1-t)t²P2 + t³P3', (r.x + 16, r.y + 64), 16, C['text'], kind='mono')
        t = min(1.0, self.ball) if self.ball is not None else 0.0
        b = cg.bezier(self.pts, t)
        text(surf, f't = {t:.2f}   B(t) = ({b[0]:.0f}, {b[1]:.0f})', (r.x + 16, r.y + 94), 16, C['parch'], kind='mono')
        cps = '  '.join(f'P{i}({p[0]:.0f},{p[1]:.0f})' for i, p in enumerate(self.pts) if i in L['drag'])
        text(surf, cps, (r.x + 16, r.y + 118), 15, C['gold'], kind='mono')
        text(surf, f'Anéis: {len(self.passed)}/{len(L["rings"])}', (r.x + 16, r.y + 140), 16, C['text'])
