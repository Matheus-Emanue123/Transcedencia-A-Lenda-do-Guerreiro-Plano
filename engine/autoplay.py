"""
autoplay.py - Modo demonstração:  python main.py --demo

Um "jogador robô" joga o jogo inteiro na janela real, usando as MESMAS
entradas de um humano: eventos de mouse (mover, clicar, arrastar), teclas
pressionadas e leitura dos diálogos. Um cursor dourado mostra onde ele está
clicando e uma legenda explica o que está fazendo. ESC encerra a demo.
"""
import math
import pygame

from .core import W, H
from .assets import text, font
from .ui import C
from . import cg

READ_BASE = 0.8        # segundos mínimos em cada fala
READ_CPS = 36          # caracteres por segundo de leitura


def ease(t):
    return t * t * (3 - 2 * t)


def nang(a):
    """Normaliza um ângulo para (-180, 180]."""
    return (a + 180) % 360 - 180


class Driver:
    def __init__(self, game):
        self.game = game
        self.cursor = [W / 2, H / 2]
        self.buttons = (0, 0, 0)
        self.pressed = set()
        self.scene_ref = None
        self.script = None
        self.wait = 0.0
        self.cond = None
        self.dt = 1 / 60
        self.caption = ''
        self.ripples = []
        self.dialog_t = 0.0
        self.finished = False
        self._real_pressed = pygame.key.get_pressed
        self._real_mouse = pygame.mouse.get_pos
        drv = self

        class _Keys:
            def __getitem__(self, k):
                return k in drv.pressed
        pygame.key.get_pressed = lambda: _Keys()
        pygame.mouse.get_pos = lambda: (int(drv.cursor[0]), int(drv.cursor[1]))

    # ------------------------------------------------------------ entrada real
    def accept_real(self, e):
        """Durante a demo, só o ESC do usuário é aceito (encerra a demonstração)."""
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.stop()
            return True
        return False

    def stop(self):
        pygame.key.get_pressed = self._real_pressed
        pygame.mouse.get_pos = self._real_mouse
        pygame.mouse.set_visible(True)
        self.game.driver = None

    # ------------------------------------------------------------ eventos
    def post(self, etype, **kw):
        self.game.scene.handle(pygame.event.Event(etype, **kw))

    def key(self, k, uni=''):
        self.post(pygame.KEYDOWN, key=k, unicode=uni, mod=0, scancode=0)
        self.post(pygame.KEYUP, key=k, unicode=uni, mod=0, scancode=0)

    # ------------------------------------------------------------ laço
    def update(self, dt):
        self.dt = dt
        self.ripples = [(x, y, t + dt) for x, y, t in self.ripples if t < 0.5]
        scene = self.game.scene
        if scene is not self.scene_ref:
            self.scene_ref = scene
            self.pressed.clear()
            self.wait, self.cond = 0.8, None
            fn = getattr(self, 's_' + type(scene).__name__.lower(), None)
            self.script = fn(scene) if fn else None
        if getattr(scene, 'show_help', False):
            scene.show_help = False
        if hasattr(scene, 'hud_hint'):
            scene.hud_hint = ''          # a legenda da demo ocupa o rodapé
        # diálogos: espera o texto terminar, dá tempo de leitura e avança
        d = getattr(scene, 'dialog', None)
        if d is not None and d.active:
            self.pressed.clear()
            full = len(d.lines[d.i][2]) if d.i < len(d.lines) else 0
            if d.chars >= full:
                self.dialog_t += dt
                if self.dialog_t > READ_BASE + full / READ_CPS:
                    self.dialog_t = 0
                    self.key(pygame.K_SPACE, ' ')
            else:
                self.dialog_t = 0
            return
        if self.script is None:
            return
        if self.wait > 0:
            self.wait -= dt
            return
        if self.cond is not None:
            if not self.cond():
                return
            self.cond = None
        try:
            r = next(self.script)
        except StopIteration:
            self.script = None
            return
        if callable(r):
            self.cond = r
        else:
            self.wait = float(r or 0)

    # ------------------------------------------------------------ primitivas
    def move(self, pos, dur=0.45):
        sx, sy = self.cursor
        t = 0.0
        while t < dur:
            t += self.dt
            k = ease(min(1.0, t / dur))
            old = tuple(self.cursor)
            self.cursor = [sx + (pos[0] - sx) * k, sy + (pos[1] - sy) * k]
            self.post(pygame.MOUSEMOTION, pos=(int(self.cursor[0]), int(self.cursor[1])),
                      rel=(int(self.cursor[0] - old[0]), int(self.cursor[1] - old[1])), buttons=self.buttons)
            yield 0
        self.cursor = [pos[0], pos[1]]

    def click(self, pos, dur=0.45, button=1):
        yield from self.move(pos, dur)
        yield 0.12
        p = (int(pos[0]), int(pos[1]))
        self.post(pygame.MOUSEBUTTONDOWN, pos=p, button=button)
        self.ripples.append((p[0], p[1], 0.0))
        yield 0.08
        self.post(pygame.MOUSEBUTTONUP, pos=p, button=button)
        yield 0.25

    def drag(self, a, b, dur=0.8):
        yield from self.move(a, 0.45)
        yield 0.1
        self.post(pygame.MOUSEBUTTONDOWN, pos=(int(a[0]), int(a[1])), button=1)
        self.buttons = (1, 0, 0)
        yield 0.1
        yield from self.move(b, dur)
        yield 0.05
        self.post(pygame.MOUSEBUTTONUP, pos=(int(b[0]), int(b[1])), button=1)
        self.buttons = (0, 0, 0)
        yield 0.25

    def slider(self, sl, value, dur=0.7):
        t = (sl.value - sl.vmin) / (sl.vmax - sl.vmin)
        a = (sl.rect.x + t * sl.rect.w, sl.rect.centery)
        t2 = (value - sl.vmin) / (sl.vmax - sl.vmin)
        b = (sl.rect.x + t2 * sl.rect.w, sl.rect.centery)
        yield from self.drag(a, b, dur)

    def type_text(self, s):
        for ch in s:
            self.key(ord(ch) if ch.isdigit() else pygame.K_PERIOD, ch)
            yield 0.15

    def hold(self, keys, cond, timeout=30.0):
        """Segura teclas até cond() ser verdadeira."""
        for k in keys:
            self.pressed.add(k)
        t = 0.0
        while not cond() and t < timeout:
            t += self.dt
            yield 0
        for k in keys:
            self.pressed.discard(k)

    def say(self, msg):
        self.caption = msg

    # ------------------------------------------------------------ desenho
    def draw(self, surf):
        pygame.mouse.set_visible(False)
        for x, y, t in self.ripples:
            pygame.draw.circle(surf, C['gold'], (x, y), int(8 + 50 * t), 2)
        x, y = self.cursor
        pts = [(x, y), (x, y + 22), (x + 6, y + 17), (x + 11, y + 27), (x + 15, y + 25), (x + 10, y + 15), (x + 17, y + 15)]
        pygame.draw.polygon(surf, (20, 14, 6), [(px + 2, py + 2) for px, py in pts])
        pygame.draw.polygon(surf, C['gold'], pts)
        pygame.draw.polygon(surf, (60, 40, 10), pts, 1)
        d = getattr(self.game.scene, 'dialog', None)
        if d is not None and d.active:
            return
        msg = '>> DEMO   ' + (self.caption or '')
        f = font(17, 'mono')
        w = f.size(msg)[0] + 28
        box = pygame.Surface((w, 32), pygame.SRCALPHA)
        pygame.draw.rect(box, (10, 6, 20, 225), box.get_rect(), border_radius=10)
        pygame.draw.rect(box, C['gold'] + (255,), box.get_rect(), 1, border_radius=10)
        r = box.get_rect(midbottom=(W // 2, H - 6))
        surf.blit(box, r)
        text(surf, msg, (r.x + 14, r.y + 6), 17, C['gold'], kind='mono', shadow=False)

    # =================================================================== ROTEIROS
    def s_menu(self, sc):
        if self.finished:
            self.say('Demonstração concluída! (ESC para sair do modo demo)')
            return
        self.say('Abrindo o jogo...')
        yield 1.5
        yield from self.move(sc.buttons[2].rect.center, 0.6)
        yield 0.4
        self.say('Iniciando a jornada')
        yield from self.click(sc.buttons[0].rect.center, 0.6)

    # ------------------------------------------------------------ prólogo
    def s_intro(self, sc):
        from scenes import intro as I
        yield lambda: sc.state == 'free'
        R = pygame.K_RIGHT

        def walk(x):
            while sc.kx < x:
                if sc.state == 'free':
                    self.pressed.add(R)
                # porteira trancada: o aviso já apareceu e o cavaleiro está encostado nela
                if not sc.quest and getattr(sc, '_gate_msg', 0) and sc.kx >= I.GATE_X - 31 and sc.state == 'free':
                    break
                yield 0
            self.pressed.discard(R)
            yield 0.25

        def talk():
            yield 0.2
            if sc.near is not None and sc.state == 'free':
                self.key(pygame.K_e, 'e')
            yield 0.4

        self.say('Andando pelo vilarejo com as setas')
        yield from walk(610)
        self.say('Conversando com o Guarda Rufus (E)')
        yield from talk()
        self.say('Pulando (ESPAÇO)')
        self.key(pygame.K_SPACE, ' ')
        yield 0.8
        yield from walk(990)
        self.say('Conversando com o Ferreiro Bento')
        yield from talk()
        yield from walk(1330)
        self.say('Conversando com a Aldeã Lia')
        yield from talk()
        yield from walk(1630)
        self.say('Conversando com Bolinha, o slime')
        yield from talk()
        yield from walk(1940)
        self.say('Conversando com o Ancião Euclides')
        yield from talk()
        self.say('Indo até a porteira leste...')
        yield from walk(I.GATE_X)
        yield lambda: sc.state == 'free'
        yield 0.3
        self.say('Recebendo a missão do Capitão Ortogonal')
        yield from talk()
        yield lambda: sc.state == 'free' and sc.gate_open >= 1
        self.say('Patrulhando os arredores a leste')
        while sc.state != 'volumar':
            if sc.state == 'free':
                self.pressed.add(R)
            yield 0
        self.pressed.discard(R)

    # ------------------------------------------------------------ fase I
    def s_fase1(self, sc):
        from scenes.fase1_raster import CELL, Y0
        cell = lambda c, r: (c * CELL + 8, Y0 + r * CELL + 8)
        self.say('Bresenham: tentando uma única reta até o outro penhasco...')
        yield from self.click(cell(14, 28), 0.8)
        yield from self.click(cell(62, 20), 0.9)
        yield lambda: sc.anim is None
        yield 1.2
        self.say('A reta tocou os pixels corrompidos. Indo por baixo da coluna: 1º segmento')
        yield from self.click(cell(41, 26), 0.9)
        yield lambda: sc.anim is None
        yield 0.6
        self.say('2º segmento até o topo do penhasco direito (inclinação ≤ 45°)')
        yield from self.click(cell(62, 20), 0.9)
        yield lambda: sc.state == 'circle'
        self.say('Ponto Médio: testando raio r = 5')
        yield 0.8
        for _ in range(2):
            self.key(pygame.K_UP)
            yield 0.4
        self.key(pygame.K_RETURN)
        yield lambda: sc.circle_anim is None
        yield 1.4
        self.say('As runas estão a distância √(Δx²+Δy²) ≈ 6 do centro: r = 6')
        self.key(pygame.K_UP)
        yield 0.6
        self.key(pygame.K_RETURN)

    # ------------------------------------------------------------ fase II
    def s_fase2(self, sc):
        yield lambda: sc.walk_to is None
        self.say('RGB aditivo: alvo laranja (255,140,0)')
        yield from self.slider(sc.sliders[0], 255)
        yield from self.slider(sc.sliders[1], 200)
        self.say('Primeira tentativa com G = 200...')
        yield from self.click(sc.confirm.rect.center)
        yield 1.6
        self.say('A dica diz "G alto": baixando o verde para 140')
        yield from self.slider(sc.sliders[1], 140)
        yield from self.click(sc.confirm.rect.center)
        yield lambda: sc.gi == 1 and sc.walk_to is None
        self.say('CMYK subtrativo: R = 255(1-C)(1-K) = 51  ->  C = 75%, K = 20%')
        yield from self.slider(sc.sliders[0], 75)
        yield from self.slider(sc.sliders[1], 50)
        yield from self.slider(sc.sliders[3], 20)
        yield from self.click(sc.confirm.rect.center)
        yield lambda: sc.gi == 2 and sc.walk_to is None
        self.say('Alpha: C = αF + (1-α)B  ->  α = 0.65')
        yield from self.slider(sc.sliders[0], 0.4)
        yield from self.click(sc.confirm.rect.center)
        yield 1.6
        yield from self.slider(sc.sliders[0], 0.65)
        yield from self.click(sc.confirm.rect.center)

    # ------------------------------------------------------------ fase III
    def s_fase3(self, sc):
        from scenes.fase3_chroma import OY
        self.say('Conta-gotas: escolhendo a cor-chave no véu verde')
        yield from self.click((900, OY + 250), 0.9)
        yield 0.5
        self.say('Tolerância alta demais...')
        yield from self.slider(sc.tol, 150, 1.0)
        yield 0.8
        yield from self.click(sc.cast.rect.center)
        yield 1.8
        self.say('...apagou a floresta real! Reduzindo a tolerância para 60')
        yield from self.slider(sc.tol, 60, 1.0)
        yield 0.8
        yield from self.click(sc.cast.rect.center)

    # ------------------------------------------------------------ fase IV
    def s_fase4(self, sc):
        def op(k, vals):
            yield from self.click(sc.op_buttons[k].rect.center, 0.4)
            for p, v in zip(sc.params, vals):
                yield from self.slider(p, v, 0.6)
            yield from self.click(sc.apply_b.rect.center, 0.4)
            yield 0.3

        seqs = [
            ('Translação T(4, 2.5)', [(0, [4, 2.5])]),
            ('Rotação de 90° e depois translação', [(2, [90]), (0, [-4, 1.5])]),
            None,
            ('Reflexão em Y e depois cisalhamento (a ordem importa!)', [(4, []), (5, [0.5, 0])]),
            ('Rotação e escala em torno do centro: T(c)·R·S·T(-c)', [(0, [4, -2]), (1, [0.75, 0.75]), (2, [-135]), (0, [-4, 2])]),
        ]
        for i, item in enumerate(seqs):
            yield lambda: sc.li == i and not sc.opening
            yield 0.6
            if item is None:
                self.say('Escalar 1.75x direto escala em relação à ORIGEM... (erro)')
                yield from op(1, [1.75, 1.75])
                yield 1.5
                self.say('Desfazendo. Correto: T(-c), S, T(c)')
                yield from self.click(sc.undo_b.rect.center)
                for k, v in [(0, [-4, 3]), (1, [1.75, 1.75]), (0, [4, -3])]:
                    yield from op(k, v)
            else:
                self.say(item[0])
                for k, v in item[1]:
                    yield from op(k, v)

    # ------------------------------------------------------------ fase V
    def s_fase5(self, sc):
        from scenes.fase5_coords import ROUNDS
        for i, R in enumerate(ROUNDS):
            yield lambda: sc.ri == i and sc.shot is None
            yield 0.6
            x, y = cg.sru_to_srd(*R['target'], R['win'], R['vp'])
            if R['mode'] == 'click':
                xn, yn = cg.sru_to_srn(*R['target'], R['win'])
                self.say(f'SRU {R["target"]} -> SRN ({xn:.2f},{yn:.2f}) -> SRD ({x:.0f},{y:.0f})')
                yield from self.click((x, y), 1.0)
            else:
                self.say(f'Noite: calculando xd = {x:.0f}, yd = {y:.0f} e digitando')
                yield from self.click(sc.inx.rect.center)
                yield from self.type_text(f'{x:.0f}')
                yield from self.click(sc.iny.rect.center)
                yield from self.type_text(f'{y:.0f}')
                yield 0.4
                yield from self.click(sc.fire_b.rect.center)
            yield lambda: sc.shot is None
            yield 1.0

    # ------------------------------------------------------------ fase VI
    def s_fase6(self, sc):
        sol = [[(1, (320, 60))], [(1, (290, 680)), (2, (800, 80))], [(1, (200, 680)), (2, (590, 230))]]
        self.say('Lançando sem ajustar... (vai bater no pilar)')
        yield 0.8
        self.key(pygame.K_SPACE, ' ')
        yield lambda: sc.ball is None
        yield 1.2
        for li, moves in enumerate(sol):
            yield lambda: sc.li == li and not sc.won_t
            yield 0.5
            self.say(f'Feitiço {li + 1}: arrastando os pontos de controle')
            for i, pos in moves:
                yield from self.drag(tuple(sc.pts[i]), pos, 1.0)
            self.say('ESPAÇO: lançar (veja a construção de De Casteljau)')
            yield 0.5
            self.key(pygame.K_SPACE, ' ')
            yield lambda: sc.ball is None
            yield 1.0

    # ------------------------------------------------------------ fase VII
    def s_fase7(self, sc):
        from scenes.fase7_proj import CHALLENGES
        K = pygame
        for ci, ch in enumerate(CHALLENGES):
            yield lambda: sc.ci == ci and not sc.ok_t
            yield 0.8
            tx, ty, tz = ch['rot']
            if ch['mode'] == 'persp':
                self.say('Trocando para projeção PERSPECTIVA (P)')
                self.key(K.K_p, 'p')
                yield 0.8
            self.say(f'Girando o objeto para rotX={tx:.0f}°, rotY={ty:.0f}°, rotZ={tz:.0f}°')
            while not sc.ok_t and sc.ci == ci:
                self.pressed.clear()
                dy, dx, dz = nang(ty - sc.ry), nang(tx - sc.rx), nang(tz - sc.rz)
                axis = next(((d, a) for d, a in ((dy, 'y'), (dx, 'x'), (dz, 'z')) if abs(d) > 0.4), None)
                if axis:
                    d, a = axis
                    keys = {'y': (K.K_RIGHT, K.K_LEFT), 'x': (K.K_DOWN, K.K_UP), 'z': (K.K_e, K.K_q)}[a]
                    self.pressed.add(keys[0] if d > 0 else keys[1])
                    if abs(d) < 6:
                        self.pressed.add(K.K_LSHIFT)
                elif ch['mode'] == 'persp':
                    self.say(f'Ajustando a distância focal d -> {ch["d"]} (W/S)')
                    dd = ch['d'] - sc.d
                    self.pressed.add(K.K_w if dd > 0 else K.K_s)
                    if abs(dd) < 0.3:
                        self.pressed.add(K.K_LSHIFT)
                yield 0
            self.pressed.clear()
            yield 0.5

    # ------------------------------------------------------------ fase VIII
    def s_fase8(self, sc):
        from scenes.fase8_revol import TASKS, e2s
        for ti, T in enumerate(TASKS):
            yield lambda: sc.ti == ti and not sc.ok_t
            yield 0.6
            self.say(f'{T["name"]}: arrastando os pontos para seguir o molde')
            for i in T['drag']:
                yield from self.drag(e2s(sc.pts[i]), e2s(T['target'][i]), 0.9)
            if ti == 0:
                self.say(f'Forjando com n = {int(sc.seg.value)} segmentos...')
                yield from self.click(sc.forge_b.rect.center)
                yield 1.8
                self.say('Peça facetada! Aumentando para n = 20 segmentos')
            yield from self.slider(sc.seg, 20, 0.8)
            yield 0.8
            yield from self.click(sc.forge_b.rect.center)

    # ------------------------------------------------------------ fase IX
    def s_fase9(self, sc):
        import numpy as np
        K = pygame
        last_pos, stuck_t, strafe_t, side = sc.pos.copy(), 0.0, 0.0, 1
        self.say('Explorando o mundo 3D: W anda, setas giram a câmera')
        while sc.state == 'explore':
            self.pressed.clear()
            targets = [c for c, g in zip(sc.crystals, sc.got) if not g]
            if not targets:
                yield 0
                continue
            tgt = min(targets, key=lambda c: np.linalg.norm((c - sc.pos)[[0, 2]]))
            dvec = tgt - sc.pos
            desired = math.degrees(math.atan2(dvec[0], dvec[2]))
            diff = nang(desired - sc.yaw)
            if abs(diff) > 3:
                self.pressed.add(K.K_LEFT if diff > 0 else K.K_RIGHT)
            if abs(diff) < 35:
                self.pressed.add(K.K_w)
                self.pressed.add(K.K_LSHIFT)          # o mapa é grande: corre
            if abs(sc.pitch - 2) > 2:
                self.pressed.add(K.K_DOWN if sc.pitch > 2 else K.K_UP)
            # desvio se ficar preso em uma árvore
            if K.K_w in self.pressed:
                stuck_t += self.dt
                if stuck_t > 0.8:
                    if np.linalg.norm(sc.pos - last_pos) < 0.5:
                        strafe_t = 0.7
                    last_pos, stuck_t = sc.pos.copy(), 0.0
            if strafe_t > 0:
                strafe_t -= self.dt
                self.pressed.add(K.K_d)
            self.say(f'Indo até o cristal ({tgt[0]:.0f}, {tgt[2]:.0f})   -   absorvidos: {sum(sc.got)}/3')
            yield 0
        self.pressed.clear()
        yield 0.5
        self.say('BATALHA: mirando com a câmera (prevendo o movimento) e desviando com A/D')
        flip_t = 0.0
        while sc.state == 'battle':
            d = sc.dragon
            self.pressed.clear()
            flip_t += self.dt
            if flip_t > 1.3:
                flip_t, side = 0.0, -side
            self.pressed.add(K.K_d if side > 0 else K.K_a)
            if d is not None:
                vel = d.get('vel', np.zeros(3))
                dist = float(np.linalg.norm(d['p'] - sc.pos))
                aim = d['p'] + vel * (dist / 42.0)
                v = aim - (sc.pos + np.array([0, -0.3, 0]))
                yaw = math.degrees(math.atan2(v[0], v[2]))
                pitch = math.degrees(math.atan2(v[1], math.hypot(v[0], v[2])))
                dy, dp = nang(yaw - sc.yaw), pitch - sc.pitch
                step = 260 * self.dt
                ry = max(-step, min(step, dy))
                rp = max(-step, min(step, dp))
                # "mouse" com o botão direito: yaw -= rel_x*0.25 ; pitch -= rel_y*0.25
                self.post(K.MOUSEMOTION, pos=(W // 2, H // 2), rel=(int(round(-ry / 0.25)), int(round(-rp / 0.25))),
                          buttons=(0, 0, 1))
                if abs(dy) < 3.5 and abs(dp) < 3.5:
                    self.key(K.K_SPACE, ' ')
                self.say(f'Vorax: {d["hp"]}/{d["max"]} de vida   -   corações: {sc.hearts}')
            yield 0
        self.pressed.clear()

    # ------------------------------------------------------------ final
    def s_ending(self, sc):
        self.say('Epílogo')
        yield lambda: sc.finished
        yield 5.0
        self.finished = True
        self.key(pygame.K_SPACE, ' ')
