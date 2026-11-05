"""
FASE V - O Mapa do Cartógrafo  (Sistemas de coordenadas: SRU -> SRN -> SRD)

O batedor informa posições em quilômetros (SRU, universo). O mapa na tela é
uma viewport (SRD, pixels). Sir Lineu precisa converter as coordenadas para
mirar a catapulta - nas duas primeiras rodadas clicando, e na última (à noite,
sem mapa visível) digitando os pixels calculados.
"""
import math
import random
import pygame

from engine.core import Phase, W, H
from engine.assets import text, text_block
from engine.ui import C, Button, TextInput, panel, parchment
from engine import cg, audio

PX = 812

ROUNDS = [
    {'win': (0, 200, 0, 120), 'vp': (40, 96, 720, 432), 'target': (150, 40), 'name': 'Acampamento goblin',
     'mode': 'click', 'grid': 20, 'labels': True},
    {'win': (80, 160, 30, 90), 'vp': (60, 80, 680, 510), 'target': (137, 52), 'name': 'Torre do Necromante',
     'mode': 'click', 'grid': 10, 'labels': False},
    {'win': (100, 300, 0, 150), 'vp': (100, 120, 600, 450), 'target': (235, 42), 'name': 'Covil de Vorax',
     'mode': 'type', 'grid': 0, 'labels': False},
]

FEATURES = {
    'river': [(0, 60), (30, 62), (60, 50), (95, 55), (130, 40), (170, 45), (210, 30), (260, 35), (300, 20)],
    'lake': [(20, 90), (40, 100), (55, 92), (48, 80), (28, 78)],
    'mountains': [(80, 100), (95, 108), (110, 98), (125, 105), (240, 110), (260, 100), (280, 115)],
    'forest': [(150, 20), (160, 15), (170, 22), (158, 28), (175, 12), (185, 25), (220, 60), (230, 70), (215, 75)],
    'castle': (40, 30),
    'village': [(115, 72), (125, 70), (120, 80)],
    'tower': [(137, 52)],
}


class Fase5(Phase):
    index = 4
    music = 'fase4'
    ambience = ['amb_fire']
    title = 'Fase V - O Mapa do Cartógrafo'
    subtitle = 'Sistemas de coordenadas'
    concept_title = 'SRU -> SRN -> SRD: transformação window/viewport'
    concept = (
        "SRO (objeto): coordenadas locais de cada modelo.   SRU (universo): o mundo da aplicação - aqui, quilômetros.\n"
        "SRN (normalizado): valores em [0,1], independentes do dispositivo.   SRD (dispositivo): pixels da tela.\n\n"
        "WINDOW = região do SRU que queremos ver: (xmin, xmax, ymin, ymax).\n"
        "VIEWPORT = retângulo da tela onde ela aparece: (vx, vy, largura, altura).\n\n"
        "1) SRU -> SRN:   xn = (xw - xmin)/(xmax - xmin)      yn = (yw - ymin)/(ymax - ymin)\n"
        "2) SRN -> SRD:   xd = vx + xn·largura                yd = vy + (1 - yn)·altura\n\n"
        "Atenção ao (1 - yn): no plano cartesiano o Y cresce para CIMA, mas na tela (plano de view) o Y cresce "
        "para BAIXO, com a origem no canto superior esquerdo.\n\n"
        "Na rodada noturna o mapa fica invisível: calcule xd e yd com as fórmulas e digite os valores."
    )
    intro = [
        ('Cartógrafo', 'king', 'Ah, o famoso cavaleiro! Meu batedor localizou os servos de Vorax, mas ele só '
                               'fala em quilômetros do reino. Já a minha mesa de mapa... só entende pixels.'),
        ('Volumar', 'wizard', 'O reino é o Sistema de Referência do Universo (SRU). O mapa na mesa é a viewport, '
                              'no Sistema de Referência do Dispositivo (SRD). Entre eles existe o SRN, normalizado.'),
        ('Batedor', 'scout', 'Acampamento goblin em (150, 40) quilômetros! Mire a catapulta clicando no mapa!'),
    ]
    outro = [
        ('Batedor', 'scout', 'Acertou em cheio! O covil foi exposto... e algo enorme levantou voo de lá.'),
        ('Volumar', 'wizard', 'Era Vorax. Ele fugiu para a Torre das Curvas, onde nada anda em linha reta. '
                              'Para persegui-lo, você precisará dominar as curvas de Bézier.'),
    ]

    def setup(self):
        self.ri = 0
        self.shot = None
        self.result = None
        self.inx = TextInput((PX + 30, 470, 180, 38), 'xd (pixels)')
        self.iny = TextInput((PX + 240, 470, 180, 38), 'yd (pixels)')
        self.fire_b = Button((PX + 30, 530, 390, 44), 'Disparar catapulta!', self.fire_typed, 20, hotkey=pygame.K_RETURN)
        self.hud_hint = 'Clique no mapa para disparar a catapulta'
        self.explosions = []

    @property
    def R(self):
        return ROUNDS[self.ri]

    def fire_typed(self):
        if self.R['mode'] != 'type' or self.shot:
            return
        x, y = self.inx.number(), self.iny.number()
        if x is None or y is None:
            self.toast('Digite números válidos para xd e yd.', C['red'])
            return
        self.launch((x, y))

    def launch(self, pos):
        vx, vy, vw, vh = self.R['vp']
        audio.sfx('wood_launch')
        audio.sfx('whoosh')
        self.shot = {'from': (vx + 20, vy + vh - 10), 'to': pos, 't': 0.0}
        self.result = None

    def on_event(self, e):
        if self.shot:
            return
        if self.R['mode'] == 'click':
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and pygame.Rect(self.R['vp']).collidepoint(e.pos):
                self.launch(e.pos)
        else:
            self.inx.handle(e)
            self.iny.handle(e)
            self.fire_b.handle(e)

    def on_update(self, dt, paused):
        self.explosions = [(x, y, t - dt) for x, y, t in self.explosions if t > 0]
        if paused or not self.shot:
            return
        s = self.shot
        s['t'] += dt * 1.1
        if s['t'] >= 1:
            pos = s['to']
            self.explosions.append((pos[0], pos[1], 0.8))
            tx, ty = cg.sru_to_srd(*self.R['target'], self.R['win'], self.R['vp'])
            err = math.hypot(pos[0] - tx, pos[1] - ty)
            uw = cg.srd_to_sru(pos[0], pos[1], self.R['win'], self.R['vp'])
            self.result = {'click': pos, 'sru': uw, 'true': (tx, ty), 'err': err}
            self.shot = None
            tol = 8 if self.R['mode'] == 'type' else 16
            audio.sfx('explosion' if err <= tol else 'thud')
            if err <= tol:
                self.toast(f'{self.R["name"]} atingido!', C['green'])
                self.result['hit'] = True
                if self.ri < len(ROUNDS) - 1:
                    self.ri += 1
                    self.result = None
                    nxt = [None,
                           [('Batedor', 'scout', 'A Torre do Necromante fica em (137, 52) km!'),
                            ('Cartógrafo', 'king', 'Ampliei o mapa: a window agora mostra só uma parte do reino, e a '
                                                   'viewport mudou de tamanho. As marcações sumiram... calcule bem!')],
                           [('Cartógrafo', 'king', 'Anoiteceu! Não consigo ver nada no mapa.'),
                            ('Batedor', 'scout', 'O Covil de Vorax fica em (235, 42) km!'),
                            ('Volumar', 'wizard', 'Sem mapa, só a matemática salva. Calcule xd e yd com as fórmulas '
                                                  'do painel e digite os valores. Os parâmetros da window e da viewport estão lá.')]]
                    self.say(nxt[self.ri])
                    self.hud_hint = 'Clique no mapa para disparar a catapulta' if self.R['mode'] == 'click' \
                        else 'Digite xd e yd e pressione ENTER'
                else:
                    self.complete()
            else:
                self.toast(f'Errou por {err:.0f} pixels. Veja o cálculo no painel.', C['red'])

    # ---------------------------------------------------------------- desenho
    def draw_map(self, surf):
        R = self.R
        win, vp = R['win'], R['vp']
        rect = pygame.Rect(vp)
        night = R['mode'] == 'type'
        if night:
            pygame.draw.rect(surf, (10, 12, 26), rect)
            for i in range(60):
                x = rect.x + (i * 7919) % rect.w
                y = rect.y + (i * 6271) % rect.h
                pygame.draw.circle(surf, (200, 200, 230), (x, y), 1)
        else:
            parchment(surf, rect)
        clip = surf.get_clip()
        surf.set_clip(rect)
        f = lambda p: cg.sru_to_srd(p[0], p[1], win, vp)
        if not night:
            g = R['grid']
            if g:
                x = math.ceil(win[0] / g) * g
                while x <= win[1]:
                    xd, _ = f((x, win[2]))
                    pygame.draw.line(surf, (190, 165, 120), (xd, rect.top), (xd, rect.bottom))
                    if R['labels']:
                        text(surf, f'{x}', (xd + 3, rect.bottom - 20), 14, C['ink'], kind='mono', shadow=False)
                    x += g
                y = math.ceil(win[2] / g) * g
                while y <= win[3]:
                    _, yd = f((win[0], y))
                    pygame.draw.line(surf, (190, 165, 120), (rect.left, yd), (rect.right, yd))
                    if R['labels']:
                        text(surf, f'{y}', (rect.x + 4, yd + 2), 14, C['ink'], kind='mono', shadow=False)
                    y += g
            pygame.draw.lines(surf, (70, 120, 200), False, [f(p) for p in FEATURES['river']], 6)
            pygame.draw.polygon(surf, (90, 140, 210), [f(p) for p in FEATURES['lake']])
            sx = rect.w / (win[1] - win[0])
            for p in FEATURES['mountains']:
                x, y = f(p)
                s = 6 * sx
                pygame.draw.polygon(surf, (120, 100, 80), [(x - s, y + s * 0.6), (x, y - s), (x + s, y + s * 0.6)])
                pygame.draw.polygon(surf, (240, 240, 240), [(x - s * 0.3, y - s * 0.4), (x, y - s), (x + s * 0.3, y - s * 0.4)])
            sc = max(1, min(5, int(sx * 1.2)))
            for p in FEATURES['forest']:
                img = self.assets.sprite('tree_pine', sc)
                surf.blit(img, img.get_rect(center=f(p)))
            img = self.assets.sprite('castle_top', sc + 1)
            surf.blit(img, img.get_rect(center=f(FEATURES['castle'])))
            for p in FEATURES['village']:
                img = self.assets.sprite('roof_red_top', sc)
                surf.blit(img, img.get_rect(center=f(p)))
            if self.ri >= 2:
                img = self.assets.sprite('pillar', sc)
                surf.blit(img, img.get_rect(center=f(FEATURES['tower'][0])))
        # resultado do último disparo
        if self.result:
            cx, cy = self.result['click']
            pygame.draw.circle(surf, C['red'], (int(cx), int(cy)), 8, 2)
            tx, ty = self.result['true']
            if not self.result.get('hit'):
                pygame.draw.circle(surf, C['green'], (int(tx), int(ty)), 10, 2)
                pygame.draw.line(surf, C['green'], (tx - 14, ty), (tx + 14, ty), 1)
                pygame.draw.line(surf, C['green'], (tx, ty - 14), (tx, ty + 14), 1)
        for x, y, t in self.explosions:
            rr = int(40 * (1 - t / 0.8)) + 4
            pygame.draw.circle(surf, (255, 160, 40), (int(x), int(y)), rr, 4)
            pygame.draw.circle(surf, (255, 230, 120), (int(x), int(y)), rr // 2)
        if self.shot:
            s = self.shot
            t = s['t']
            a, b = s['from'], s['to']
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t - 180 * math.sin(math.pi * t)
            pygame.draw.circle(surf, (60, 50, 40), (int(x), int(y)), 8)
        # cursor de mira
        m = pygame.mouse.get_pos()
        if R['mode'] == 'click' and rect.collidepoint(m) and not self.shot:
            pygame.draw.circle(surf, C['red'], m, 14, 2)
            pygame.draw.line(surf, C['red'], (m[0] - 20, m[1]), (m[0] + 20, m[1]))
            pygame.draw.line(surf, C['red'], (m[0], m[1] - 20), (m[0], m[1] + 20))
        surf.set_clip(clip)
        pygame.draw.rect(surf, C['border'], rect, 3)
        # rótulos dos limites da window + viewport
        vx, vy, vw, vh = vp
        text(surf, f'xmin={win[0]}', (vx, vy + vh + 6), 15, C['parch'], kind='mono')
        text(surf, f'xmax={win[1]}', (vx + vw, vy + vh + 6), 15, C['parch'], kind='mono', right=True)
        text(surf, f'ymax={win[3]}', (vx + 6, vy - 22), 15, C['parch'], kind='mono')
        text(surf, f'ymin={win[2]}', (vx + 6, vy + vh + 26), 15, C['parch'], kind='mono')
        text(surf, f'({vx},{vy})px', (vx + vw, vy - 22), 14, C['dim'], kind='mono', right=True)
        catap = self.assets.sprite('barrel', 2)
        surf.blit(catap, (vx + 10, vy + vh - 32))

    def on_draw(self, surf):
        floor = self.assets.sprite('floor', 3)
        for x in range(0, W, 48):
            for y in range(40, H, 48):
                surf.blit(floor, (x, y))
        dark = pygame.Surface((W, H), pygame.SRCALPHA)
        dark.fill((20, 10, 0, 140))
        surf.blit(dark, (0, 0))
        self.draw_map(surf)
        self.draw_panel(surf)

    def draw_panel(self, surf):
        r = pygame.Rect(PX, 50, W - PX - 12, 650)
        panel(surf, r, alpha=240)
        R = self.R
        win, vp = R['win'], R['vp']
        text(surf, f'Rodada {self.ri + 1}/3 - {R["name"]}', (r.x + 16, r.y + 10), 22, C['gold'])
        text(surf, f'Alvo no SRU: ({R["target"][0]}, {R["target"][1]}) km', (r.x + 16, r.y + 44), 20, C['text'])
        text(surf, f'Window  (SRU): x:[{win[0]}, {win[1]}]  y:[{win[2]}, {win[3]}]', (r.x + 16, r.y + 80), 16, C['parch'], kind='mono')
        text(surf, f'Viewport(SRD): vx={vp[0]} vy={vp[1]} L={vp[2]} A={vp[3]}', (r.x + 16, r.y + 104), 16, C['parch'], kind='mono')
        text(surf, 'xn = (xw - xmin) / (xmax - xmin)', (r.x + 16, r.y + 140), 16, C['text'], kind='mono')
        text(surf, 'yn = (yw - ymin) / (ymax - ymin)', (r.x + 16, r.y + 162), 16, C['text'], kind='mono')
        text(surf, 'xd = vx + xn · L', (r.x + 16, r.y + 190), 16, C['text'], kind='mono')
        text(surf, 'yd = vy + (1 - yn) · A', (r.x + 16, r.y + 212), 16, C['text'], kind='mono')
        # mini-mapa: o SRU inteiro com a window marcada
        mm = pygame.Rect(r.x + 16, r.y + 244, 200, 120)
        pygame.draw.rect(surf, (60, 50, 40), mm)
        full = (0, 300, 0, 150)
        p0 = cg.sru_to_srd(win[0], win[3], full, tuple(mm))
        p1 = cg.sru_to_srd(win[1], win[2], full, tuple(mm))
        pygame.draw.rect(surf, C['gold'], pygame.Rect(p0, (p1[0] - p0[0], p1[1] - p0[1])), 2)
        pygame.draw.rect(surf, C['border_dark'], mm, 2)
        text(surf, 'SRU completo', (mm.right + 10, mm.y), 15, C['dim'])
        text(surf, 'e a window', (mm.right + 10, mm.y + 20), 15, C['dim'])
        text(surf, '(retângulo dourado)', (mm.right + 10, mm.y + 40), 15, C['dim'])
        y = r.y + 380
        m = pygame.mouse.get_pos()
        if self.ri == 0 and pygame.Rect(vp).collidepoint(m):
            xw, yw = cg.srd_to_sru(m[0], m[1], win, vp)
            xn, yn = cg.sru_to_srn(xw, yw, win)
            text(surf, f'Mouse: SRD ({m[0]}, {m[1]}) px', (r.x + 16, y), 16, C['parch'], kind='mono')
            text(surf, f'    -> SRN ({xn:.3f}, {yn:.3f})', (r.x + 16, y + 22), 16, C['parch'], kind='mono')
            text(surf, f'    -> SRU ({xw:.1f}, {yw:.1f}) km', (r.x + 16, y + 44), 16, C['parch'], kind='mono')
            text(surf, '(só nesta rodada de treino!)', (r.x + 16, y + 68), 15, C['dim'])
            y += 100
        if R['mode'] == 'type':
            self.inx.draw(surf)
            self.iny.draw(surf)
            self.fire_b.draw(surf)
            y = 590
        if self.result:
            res = self.result
            cx, cy = res['click']
            xw, yw = res['sru']
            tx, ty = res['true']
            col = C['green'] if res.get('hit') else C['red']
            text(surf, f'Disparo em SRD ({cx:.0f}, {cy:.0f}) px', (r.x + 16, y), 16, col, kind='mono')
            text(surf, f'  -> SRU ({xw:.1f}, {yw:.1f}) km', (r.x + 16, y + 22), 16, col, kind='mono')
            if not res.get('hit'):
                text(surf, f'Correto: SRD ({tx:.0f}, {ty:.0f}) px', (r.x + 16, y + 44), 16, C['green'], kind='mono')
