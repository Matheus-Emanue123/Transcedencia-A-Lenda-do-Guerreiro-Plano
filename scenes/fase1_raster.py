"""
FASE I - O Mundo de Pixels  (Rasterização)

O mundo é uma grade monocromática. Para atravessar o abismo, Sir Lineu
constrói pontes rasterizadas com o algoritmo de Bresenham; depois, abre um
portal desenhando uma circunferência com o algoritmo do Ponto Médio.
"""
import math
import random
import pygame

from engine.core import Phase, W, H
from engine.assets import text
from engine.ui import C, panel
from engine import cg, audio

CELL = 16
Y0 = 48
COLS, ROWS = 80, 42
G = (90, 255, 120)        # fósforo verde (monitor CRT)
G_DIM = (20, 70, 32)
G_MID = (40, 150, 64)
MAX_SEG = 3
PORTAL_C = (69, 11)
PORTAL_R = 6


class Fase1(Phase):
    index = 0
    music = 'fase1'
    ambience = ['amb_crt']
    sound_style = '8bit'
    title = 'Fase I - O Mundo de Pixels'
    subtitle = 'Rasterização'
    concept_title = 'Rasterização de primitivas: Bresenham e Ponto Médio'
    concept = (
        "A tela é uma matriz discreta de pixels (framebuffer). Uma reta matemática y = mx + b é contínua, "
        "então precisamos decidir QUAIS pixels acender - isso é rasterizar.\n\n"
        "ALGORITMO DE BRESENHAM (1962): usa apenas somas e subtrações de inteiros.\n"
        "  dx = |x1-x0|,  dy = |y1-y0|,  erro = dx - dy\n"
        "  a cada passo: pinta (x,y);  e2 = 2*erro\n"
        "     se e2 > -dy:  erro -= dy;  x += passoX\n"
        "     se e2 <  dx:  erro += dx;  y += passoY\n\n"
        "Regra do cavaleiro: ele só caminha em rampas de até 45°, isto é, |Δy| ≤ |Δx| (octantes x-dominantes). "
        "Pixels corrompidos por Vorax (e a rocha) destroem a ponte.\n\n"
        "PONTO MÉDIO (circunferência): calcula apenas 1/8 do círculo e espelha os outros 7 octantes por simetria "
        "(x,y),(y,x),(-x,y)... Decisão: d = 1 - r; se d < 0: d += 2x+3; senão: d += 2(x-y)+5 e y -= 1.\n"
        "Para abrir o portal, escolha o raio r que faz a circunferência rasterizada passar pelas 4 runas "
        "(dica: r ≈ √(Δx² + Δy²))."
    )
    intro = [
        ('Volumar', 'wizard', 'Este é o seu mundo, Lineu: uma grade de pixels. Nada aqui é contínuo. '
                              'Para cruzar o Abismo do Vazio, você precisará construir uma ponte.'),
        ('Volumar', 'wizard', 'Clique numa célula do topo do penhasco e depois no destino. O algoritmo de '
                              'Bresenham decidirá quais pixels acender. Você pode usar até 3 segmentos.'),
        ('Sir Lineu', 'knight', 'Mas cuidado com aqueles pixels tremendo... parecem corrompidos!'),
        ('Volumar', 'wizard', 'São marcas de Vorax. Se sua reta tocar neles, ela se desfaz. E lembre: '
                              'você não escala rampas mais íngremes que 45°. Pressione H para ler o pergaminho.'),
    ]
    outro = [
        ('Volumar', 'wizard', 'Magnífico! Retas e circunferências: as primitivas de todo desenho. '
                              'Mas seu mundo ainda é verde e preto... sem cor alguma.'),
        ('Sir Lineu', 'knight', 'Cor? O que é... cor?'),
        ('Volumar', 'wizard', 'Venha. O portal o levará ao Vale das Cores.'),
    ]

    def setup(self):
        self.solid = set()
        for c in range(0, 15):
            for r in range(28, ROWS):
                self.solid.add((c, r))
        for c in range(62, COLS):
            for r in range(20, ROWS):
                self.solid.add((c, r))
        for c in range(35, 42):
            for r in range(31, ROWS):
                self.solid.add((c, r))
        self.corrupt = set()
        for c in range(37, 41):
            for r in range(0, 25):
                self.corrupt.add((c, r))
        for c in range(48, 53):
            for r in range(25, ROWS):
                self.corrupt.add((c, r))
        for c, r in [(24, 22), (25, 22), (24, 23), (25, 23), (56, 14), (57, 14), (56, 15), (57, 15)]:
            self.corrupt.add((c, r))
        self.segments = []         # listas de células definitivas
        self.anim = None           # segmento sendo rasterizado
        self.start = None
        self.hover = None
        self.state = 'bridge'
        self.knight = [4.0, 28.0]
        self.path = []
        self.path_i = 0.0
        self.shatter = []
        self.radius = 3
        self.circle_anim = None
        self.circle_cells = []
        self.portal_open = 0.0
        steps = cg.midpoint_circle(PORTAL_C[0], PORTAL_C[1], PORTAL_R)
        mid = steps[len(steps) // 2][1]
        self.runes = [mid[0], mid[2], mid[5], mid[7]]
        self.hud_hint = 'Clique: origem e destino da reta   •   Botão direito: desfazer'

    # ---------------------------------------------------------------- helpers
    def cell_at(self, pos):
        c, r = pos[0] // CELL, (pos[1] - Y0) // CELL
        if 0 <= c < COLS and 0 <= r < ROWS:
            return (c, r)
        return None

    def chain_end(self):
        return self.segments[-1][-1] if self.segments else None

    def valid_start(self, cell):
        if self.segments:
            return cell == self.chain_end()
        return cell in self.solid and cell[0] <= 14 and (cell[0], cell[1] - 1) not in self.solid

    # ---------------------------------------------------------------- eventos
    def on_event(self, e):
        if self.state == 'bridge' and self.anim is None:
            if e.type == pygame.MOUSEMOTION:
                self.hover = self.cell_at(e.pos)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3 or \
                    (e.type == pygame.KEYDOWN and e.key == pygame.K_BACKSPACE):
                if self.start and not self.segments:
                    self.start = None
                    audio.sfx('ui_back')
                elif self.segments:
                    self.segments.pop()
                    self.start = self.chain_end()
                    audio.sfx('shatter2')
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                cell = self.cell_at(e.pos)
                if not cell:
                    return
                if self.start is None:
                    if self.valid_start(cell):
                        self.start = cell
                        audio.sfx('ui_select')
                    else:
                        self.toast('Comece no topo do penhasco esquerdo!', C['red'])
                else:
                    if cell == self.start:
                        return
                    if len(self.segments) >= MAX_SEG:
                        self.toast(f'Máximo de {MAX_SEG} segmentos! Desfaça um (botão direito).', C['red'])
                        return
                    dx, dy = abs(cell[0] - self.start[0]), abs(cell[1] - self.start[1])
                    if dy > dx:
                        self.toast('Rampa > 45°: |Δy| > |Δx|. O cavaleiro não escala isso!', C['red'])
                        return
                    if cell[0] < self.start[0]:
                        self.toast('A ponte deve avançar para a direita!', C['red'])
                        return
                    audio.sfx('ui_confirm')
                    self.anim = {'steps': cg.bresenham(self.start[0], self.start[1], cell[0], cell[1]),
                                 'i': 0.0, 'a': self.start, 'b': cell, 'cells': []}
        elif self.state == 'circle' and self.circle_anim is None and self.portal_open == 0:
            if e.type == pygame.MOUSEWHEEL:
                self.radius = max(1, min(10, self.radius + e.y))
                audio.sfx('ui_scroll')
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_RIGHT, pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                    self.radius = min(10, self.radius + 1)
                    audio.sfx('ui_scroll')
                elif e.key in (pygame.K_DOWN, pygame.K_LEFT, pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.radius = max(1, self.radius - 1)
                    audio.sfx('ui_scroll')
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    audio.sfx('spell2')
                    self.circle_anim = {'steps': cg.midpoint_circle(PORTAL_C[0], PORTAL_C[1], self.radius), 'i': 0.0}
                    self.circle_cells = []

    # ---------------------------------------------------------------- update
    def on_update(self, dt, paused):
        self.shatter = [(x, y, vx, vy + 400 * dt, t - dt) for x, y, vx, vy, t in self.shatter if t > 0]
        self.shatter = [(x + vx * dt, y + vy * dt, vx, vy, t) for x, y, vx, vy, t in self.shatter]
        if paused:
            return
        if self.anim:
            a = self.anim
            prev = int(a['i'])
            a['i'] += dt * 26
            for k in range(prev, min(int(a['i']), len(a['steps']))):
                x, y, _ = a['steps'][k]
                cell = (x, y)
                is_end = k == 0 or k == len(a['steps']) - 1
                if cell in self.corrupt or (cell in self.solid and not is_end):
                    self.break_segment(a['cells'] + [cell],
                                       'A reta tocou um pixel corrompido!' if cell in self.corrupt else 'A reta atravessou a rocha!')
                    return
                a['cells'].append(cell)
                audio.sfx('pixel')
            if int(a['i']) >= len(a['steps']):
                self.segments.append(a['cells'])
                audio.sfx('ui_drop')
                self.start = a['b']
                self.anim = None
                end = a['b']
                if end in self.solid and end[0] >= 62 and (end[0], end[1] - 1) not in self.solid:
                    self.begin_walk()
        if self.state == 'walk':
            before = int(self.path_i)
            self.path_i += dt * 9
            if int(self.path_i) // 2 != before // 2:
                audio.sfx('step_stone')
            if self.path_i >= len(self.path) - 1:
                self.path_i = len(self.path) - 1
                self.state = 'circle'
                self.hud_hint = 'Roda do mouse / setas: raio r   •   ENTER: rasterizar circunferência'
                self.say([('Volumar', 'wizard', 'Você cruzou o abismo! Agora abra o portal: escolha o raio r '
                                                'de modo que a circunferência passe pelas 4 runas brilhantes.'),
                          ('Volumar', 'wizard', f'O centro do portal é ({PORTAL_C[0]}, {PORTAL_C[1]}). Use as '
                                                'coordenadas das runas para calcular a distância.')])
            i = int(self.path_i)
            f = self.path_i - i
            a = self.path[i]
            b = self.path[min(i + 1, len(self.path) - 1)]
            self.knight = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
        if self.circle_anim:
            ca = self.circle_anim
            ca['i'] += dt * 5
            n = min(int(ca['i']), len(ca['steps']))
            if n > len(self.circle_cells):
                audio.sfx('pixel2')
            self.circle_cells = ca['steps'][:n]
            if int(ca['i']) >= len(ca['steps']) + 3:
                pts = {p for _, ps in ca['steps'] for p in ps}
                if all(rn in pts for rn in self.runes):
                    self.portal_open = 0.01
                    audio.sfx('portal_open')
                    audio.sfx('magic_chime')
                    self.toast('O portal se abriu!', C['green'])
                else:
                    hit = sum(rn in pts for rn in self.runes)
                    self.toast(f'r = {self.radius}: {hit}/4 runas tocadas. Tente outro raio.', C['red'])
                    self.circle_cells = []
                self.circle_anim = None
        if self.portal_open > 0:
            if self.portal_open <= 1.2 < self.portal_open + dt:
                audio.sfx('portal_whoosh')
                audio.sfx('phase_jump')
            self.portal_open += dt
            if self.portal_open > 1.2:
                self.knight[1] -= dt * 6
            if self.portal_open > 2.6:
                self.complete()

    def break_segment(self, cells, msg):
        for c, r in cells:
            for _ in range(2):
                self.shatter.append((c * CELL + 8, Y0 + r * CELL + 8, random.uniform(-120, 120),
                                     random.uniform(-200, 0), 1.2))
        audio.sfx('ui_glitch')
        audio.sfx('shatter')
        self.anim = None
        self.toast(msg, C['red'])

    def begin_walk(self):
        start = self.segments[0][0]
        path = [(c, 28) for c in range(4, start[0])]
        for seg in self.segments:
            for cell in seg:
                if not path or path[-1] != cell:
                    path.append(cell)
        end = path[-1]
        for c in range(end[0] + 1, PORTAL_C[0] + 1):
            path.append((c, 20))
        self.path = [(float(c), float(r)) for c, r in path]
        self.path_i = 0.0
        self.state = 'walk'
        self.hud_hint = ''
        self.toast('Ponte completa! Sir Lineu atravessa...', C['green'])

    # ---------------------------------------------------------------- desenho
    def on_draw(self, surf):
        surf.fill((2, 10, 4))
        flick = (pygame.time.get_ticks() // 90) % 2
        for c in range(COLS + 1):
            pygame.draw.line(surf, (8, 26, 12), (c * CELL, Y0), (c * CELL, H))
        for r in range(ROWS + 1):
            pygame.draw.line(surf, (8, 26, 12), (0, Y0 + r * CELL), (W, Y0 + r * CELL))
        for (c, r) in self.solid:
            top = (c, r - 1) not in self.solid
            pygame.draw.rect(surf, G_MID if top else G_DIM, (c * CELL + 1, Y0 + r * CELL + 1, CELL - 2, CELL - 2))
        for (c, r) in self.corrupt:
            x, y = c * CELL, Y0 + r * CELL
            if (c + r + flick) % 2:
                pygame.draw.line(surf, (200, 255, 200), (x + 3, y + 3), (x + 12, y + 12), 2)
                pygame.draw.line(surf, (200, 255, 200), (x + 12, y + 3), (x + 3, y + 12), 2)
            else:
                pygame.draw.rect(surf, (30, 90, 40), (x + 4, y + 4, 8, 8), 1)
        # segmentos prontos
        for seg in self.segments:
            for c, r in seg:
                pygame.draw.rect(surf, G, (c * CELL + 1, Y0 + r * CELL + 1, CELL - 2, CELL - 2))
        # animação de Bresenham
        if self.anim:
            for c, r in self.anim['cells']:
                pygame.draw.rect(surf, (200, 255, 200), (c * CELL + 1, Y0 + r * CELL + 1, CELL - 2, CELL - 2))
            a, b = self.anim['a'], self.anim['b']
            pygame.draw.line(surf, (255, 255, 255), (a[0] * CELL + 8, Y0 + a[1] * CELL + 8),
                             (b[0] * CELL + 8, Y0 + b[1] * CELL + 8), 1)
        # pré-visualização: reta ideal (contínua) até o mouse
        if self.state == 'bridge' and self.anim is None and self.hover:
            hc = self.hover
            ok = self.valid_start(hc) if self.start is None else True
            pygame.draw.rect(surf, G if ok else (255, 255, 255), (hc[0] * CELL, Y0 + hc[1] * CELL, CELL, CELL), 2)
            if self.start:
                s = self.start
                pygame.draw.line(surf, (160, 220, 170), (s[0] * CELL + 8, Y0 + s[1] * CELL + 8),
                                 (hc[0] * CELL + 8, Y0 + hc[1] * CELL + 8), 1)
        if self.start and self.state == 'bridge':
            s = self.start
            pygame.draw.rect(surf, (255, 255, 255), (s[0] * CELL - 2, Y0 + s[1] * CELL - 2, CELL + 4, CELL + 4), 2)
        for x, y, _, _, t in self.shatter:
            pygame.draw.rect(surf, G, (x, y, 5, 5))
        # runas e portal
        if self.state in ('circle', 'walk') or self.portal_open:
            for rc in self.runes:
                x, y = rc[0] * CELL, Y0 + rc[1] * CELL
                k = 150 + int(100 * math.sin(self.t * 5))
                pygame.draw.rect(surf, (k, 255, k), (x - 2, y - 2, CELL + 4, CELL + 4), 2)
                pygame.draw.rect(surf, (200, 255, 200), (x + 4, y + 4, 8, 8))
            cx, cy = PORTAL_C
            pygame.draw.rect(surf, (120, 200, 130), (cx * CELL + 4, Y0 + cy * CELL + 4, 8, 8), 1)
        octcols = [(90, 255, 120), (140, 255, 160), (60, 200, 90), (180, 255, 190),
                   (90, 255, 120), (140, 255, 160), (60, 200, 90), (180, 255, 190)]
        for _, pts in self.circle_cells:
            for k, (c, r) in enumerate(pts):
                col = octcols[k] if self.portal_open == 0 else (int(150 + 100 * math.sin(self.t * 8 + k)), 255, 200)
                pygame.draw.rect(surf, col, (c * CELL + 1, Y0 + r * CELL + 1, CELL - 2, CELL - 2))
        if self.portal_open:
            cx, cy = PORTAL_C[0] * CELL + 8, Y0 + PORTAL_C[1] * CELL + 8
            for i in range(6):
                rr = int((PORTAL_R * CELL - 6) * min(1, self.portal_open) * (1 - i / 7))
                pygame.draw.circle(surf, (60 + i * 30, 255, 120 + i * 20), (cx, cy), max(1, rr), 2)
        # cavaleiro (silhueta monocromática)
        kx, ky = self.knight
        k = self.assets.mono('knight', 2, G)
        if self.portal_open > 1.2:
            sc = max(0.05, 1 - (self.portal_open - 1.2) / 1.4)
            k = pygame.transform.scale(k, (max(1, int(32 * sc)), max(1, int(32 * sc))))
        surf.blit(k, k.get_rect(midbottom=(kx * CELL + 8, Y0 + ky * CELL)))
        self.draw_panel(surf)

    def draw_panel(self, surf):
        r = pygame.Rect(16, 56, 430, 232)
        panel(surf, r, alpha=225, fill=(6, 20, 10), border=G_MID)
        mono = 'mono'
        if self.state in ('bridge', 'walk'):
            text(surf, 'BRESENHAM', (r.x + 18, r.y + 12), 14, G, kind='pixel')
            text(surf, f'Segmentos: {len(self.segments)}/{MAX_SEG}', (r.right - 18, r.y + 10), 18, G, kind=mono, right=True)
            if self.anim:
                a, b = self.anim['a'], self.anim['b']
                dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
                i = min(int(self.anim['i']), len(self.anim['steps']) - 1)
                x, y, err = self.anim['steps'][i]
                lines = [f'P0=({a[0]},{a[1]})  P1=({b[0]},{b[1]})',
                         f'dx={dx}  dy={dy}  passos={len(self.anim["steps"])}',
                         f'passo {i}:  x={x}  y={y}',
                         f'erro={err:4d}   e2=2*erro={2 * err:4d}',
                         f'e2 > -dy ? {"SIM -> x+=1" if 2 * err > -dy else "não"}',
                         f'e2 <  dx ? {"SIM -> y+=passoY" if 2 * err < dx else "não"}']
            elif self.start and self.hover and self.state == 'bridge':
                a, b = self.start, self.hover
                dx, dy = b[0] - a[0], b[1] - a[1]
                m = dy / dx if dx else float('inf')
                lines = [f'P0=({a[0]},{a[1]})  P1=({b[0]},{b[1]})',
                         f'Δx={dx}  Δy={dy}',
                         f'm = Δy/Δx = {m:.2f}' if dx else 'm = ∞ (vertical)',
                         f'|Δy| ≤ |Δx| ? {"sim" if abs(dy) <= abs(dx) else "NÃO (>45°)"}',
                         'Clique para rasterizar.']
            else:
                lines = ['Escolha o ponto inicial no topo', 'do penhasco esquerdo.', '',
                         'Somente inteiros: sem ponto', 'flutuante, sem round().']
            for i, ln in enumerate(lines):
                text(surf, ln, (r.x + 18, r.y + 44 + i * 29), 18, G, kind=mono, shadow=False)
        else:
            text(surf, 'PONTO MÉDIO', (r.x + 18, r.y + 12), 14, G, kind='pixel')
            cx, cy = PORTAL_C
            lines = [f'centro C = ({cx},{cy})    raio r = {self.radius}',
                     'runas: ' + ' '.join(f'({c},{rr})' for c, rr in self.runes[:2]),
                     '       ' + ' '.join(f'({c},{rr})' for c, rr in self.runes[2:])]
            if self.circle_cells:
                d, pts = self.circle_cells[-1]
                lines += [f'passo {len(self.circle_cells) - 1}: d = {d}',
                          f'(x,y) = ({pts[0][0] - cx},{pts[0][1] - cy}) e 7 simétricos']
            else:
                lines += ['d0 = 1 - r', 'ENTER para rasterizar']
            for i, ln in enumerate(lines):
                text(surf, ln, (r.x + 18, r.y + 44 + i * 29), 18, G, kind=mono, shadow=False)
