"""
Prólogo jogável: Planícia, o reino plano.

Sir Lineu caminha (setas) pelo vilarejo monocromático, conversa com os
aldeões, recebe do Capitão a missão de patrulhar os arredores a leste e,
no caminho, começa a questionar o próprio mundo... até que uma voz de outra
dimensão o chama.

A rolagem lateral é uma window (janela) deslizando sobre o mundo: a câmera
2D apenas translada o SRU antes de desenhar (x_tela = x_mundo - cam_x).
"""
import math
import random
import pygame

from engine.core import Scene, W, H
from engine.assets import text
from engine.ui import C, Dialog, panel
from engine import audio

GREEN = (90, 255, 120)
G_MID = (40, 150, 64)
G_DIM = (16, 60, 26)
CELL = 16
GROUND = 560              # y do chão (os pés dos personagens ficam aqui)
WORLD_W = 4200
GATE_X = 2480             # porteira do vilarejo (abre após aceitar a missão)
DOUBT_X = 3150            # Lineu começa a questionar
VOLUMAR_X = 3600          # o mago aparece
MARKER_X = 3900           # Marco da Borda

ABERTURA = [
    ('Narrador', None, 'Há muito tempo, no Reino de Planícia, tudo tinha apenas largura e altura. '
                       'Ninguém jamais ouvira falar em "profundidade".'),
    ('Narrador', None, 'Os planicianos viviam numa grade de pixels sem cor. Até as montanhas eram '
                       'apenas linhas - e linhas, diziam os sábios, eram tudo o que existia.'),
    ('Narrador', None, 'Nesta manhã, como em todas as outras, Sir Lineu, cavaleiro da guarda, se apresenta '
                       'para o serviço. (Use as SETAS para andar, ESPAÇO para pular e E para conversar.)'),
]

MISSAO_ACEITA = [
    ('Capitão Ortogonal', 'knight2', 'Sir Lineu, finalmente! Os batedores relatam pixels estranhos piscando '
                                     'além da porteira leste.'),
    ('Capitão Ortogonal', 'knight2', 'Sua missão: patrulhar os arredores do vilarejo até o Marco da Borda. '
                                     'Siga sempre para a direita... como tudo em Planícia.'),
    ('Sir Lineu', 'knight', 'Às ordens, capitão! Esquerda ou direita, eu não falho.'),
    ('Capitão Ortogonal', 'knight2', 'Vou mandar abrir a porteira. E Lineu... volte inteiro. Ou, bem, '
                                     'pelo menos com a mesma largura.'),
]

DUVIDA = [
    ('Sir Lineu', 'knight', 'Mais um dia patrulhando a borda do mundo... Sempre esquerda e direita, '
                            'cima e baixo.'),
    ('Sir Lineu', 'knight', 'O ancião diz que "atrás" e "frente" são só palavras antigas. Mas então... por que '
                            'essas palavras existem? Por que sinto que falta alguma coisa?'),
    ('Sir Lineu', 'knight', 'Se o mundo é só uma linha... o que existe fora dela?'),
]

VOLUMAR = [
    ('???', None, 'S-sir... L-lineu... você... me ouve...?'),
    ('Sir Lineu', 'knight', 'Quem está aí?! Essa voz... vem de uma direção que nem existe!'),
    ('Volumar', 'wizard', 'Sou Volumar, o Arquimago Volumétrico. Falo-lhe da TERCEIRA DIMENSÃO, '
                          'um lugar onde as coisas possuem largura, altura... e profundidade.'),
    ('Sir Lineu', 'knight', 'Você... tem COR! Eu nunca vi nada assim!'),
    ('Volumar', 'wizard', 'Seu reino nem sempre foi plano. Vorax, o Dragão Achatador, esmagou Planícia '
                          'até restarem só pixels. E agora ele quer achatar também o meu mundo.'),
    ('Sir Lineu', 'knight', 'Um dragão? Mas como posso lutar contra algo que vive numa dimensão que '
                            'eu nem consigo imaginar?'),
    ('Volumar', 'wizard', 'Aprendendo as Artes dos Geômetras - a Computação Gráfica. Cada arte '
                          'acrescenta algo ao seu mundo: retas, cores, formas, curvas... profundidade.'),
    ('Volumar', 'wizard', 'Domine-as e você transcenderá para o 3D. Comece pelo mais simples: '
                          'o pixel. Seu mundo é uma grade. Aprenda a desenhar nela!'),
    ('Sir Lineu', 'knight', 'Pela honra de Planícia... eu aceito!'),
]

# aldeões: nome, sprite, x inicial, alcance do passeio, falas (sorteadas em sequência)
ALDEOES = [
    ('Guarda Rufus', 'scout', 640, 0, [
        'Bom dia, Sir Lineu! O Capitão Ortogonal está te esperando lá na porteira leste.',
        'Dizem que o Capitão nunca dobrou uma esquina. Também, pra quê? Só existem duas direções!']),
    ('Ferreiro Bento', 'smith', 1010, 50, [
        'Forjo espadas há trinta anos e todas saem iguais: largura e altura. Meu avô jurava que existia "espessura".',
        'Martelo pra esquerda, martelo pra direita... é a vida de ferreiro em Planícia.']),
    ('Aldeã Lia', 'princess', 1380, 140, [
        'Sir Lineu! Você já se perguntou o que existe ATRÁS das coisas? Minha avó dizia que antes do Dragão havia um "lado de dentro".',
        'Às vezes, à noite, vejo os pixels do céu tremerem. Como se alguém estivesse olhando de um lugar que não existe.']),
    ('Bolinha', 'slime', 1660, 90, [
        '*bloop* *bloop*  (O slime de estimação do vilarejo pula de um lado para o outro... de um lado para o outro...)',
        '*bloop?*']),
    ('Ancião Euclides', 'king', 1960, 20, [
        'Ah, jovem Lineu. Os pergaminhos antigos falam de Vorax, o Dragão que ACHATOU o reino. Mas são só lendas... eu acho.',
        '"Frente" e "atrás"... palavras que ninguém mais usa. Os sábios dizem que nunca significaram nada. Será?']),
]

CAPITAO = ('Capitão Ortogonal', 'knight2', 2405)


class NPC:
    def __init__(self, name, spr, x, rng, lines):
        self.name, self.spr, self.home, self.rng, self.lines = name, spr, x, rng, lines
        self.x = float(x)
        self.dir = 1
        self.wait = random.uniform(0.5, 2.5)
        self.talk_i = 0
        self.walking = False

    def update(self, dt, frozen):
        if frozen or self.rng == 0:
            self.walking = False
            return
        if self.wait > 0:
            self.wait -= dt
            self.walking = False
            return
        self.walking = True
        speed = 60 if self.spr == 'slime' else 35
        self.x += self.dir * speed * dt
        if abs(self.x - self.home) > self.rng:
            self.x = self.home + self.rng * (1 if self.x > self.home else -1)
            self.dir *= -1
            self.wait = random.uniform(1.0, 3.0)
        elif random.random() < 0.004:
            self.wait = random.uniform(0.8, 2.0)


class Intro(Scene):
    def __init__(self, game):
        super().__init__(game)
        audio.music('fase1')
        audio.ambience(['amb_crt'])
        audio.get().style = '8bit'
        self.t = 0.0
        self.kx, self.ky, self.vy = 250.0, float(GROUND), 0.0
        self.face = 1
        self.on_ground = True
        self.walking = False
        self.step_t = 0.0
        self.cam = 0.0
        self.state = 'opening'
        self.quest = False
        self.gate_open = 0.0
        self.volumar_t = 0.0
        self.npcs = [NPC(*a) for a in ALDEOES]
        self.captain = NPC(CAPITAO[0], CAPITAO[1], CAPITAO[2], 0, [])
        self.near = None
        self.dialog = Dialog(self.assets, ABERTURA, self.to_free)
        self._flip = {}
        self.build_world()

    # ------------------------------------------------------------- cenário
    def spr(self, name, scale=4, flip=False):
        key = (name, scale, flip)
        if key not in self._flip:
            s = self.assets.mono(name, scale, GREEN)
            self._flip[key] = pygame.transform.flip(s, True, False) if flip else s
        return self._flip[key]

    def build_world(self):
        """Pré-desenha a camada estática (casas, árvores, chão) num Surface largo."""
        self.world = pygame.Surface((WORLD_W, H), pygame.SRCALPHA)
        w = self.world
        T = 64
        rnd = random.Random(5)
        # chão em grade de pixels
        for x in range(0, WORLD_W, CELL):
            for y in range(GROUND, H, CELL):
                col = G_MID if y == GROUND else G_DIM
                pygame.draw.rect(w, col, (x + 1, y + 1, CELL - 2, CELL - 2))

        def house(x, roof='roof_red', top='roof_red_top', width=3):
            for i in range(width):
                part = 'house_door' if i == width // 2 else 'house_win'
                w.blit(self.spr(part), (x + i * T, GROUND - T))
                w.blit(self.spr(roof), (x + i * T, GROUND - 2 * T))
            w.blit(self.spr(top), (x + (width // 2) * T, GROUND - 3 * T))

        def tree(x, kind='tree'):
            img = self.spr(kind)
            w.blit(img, img.get_rect(midbottom=(x, GROUND + 4)))

        # casa/quartel de Lineu
        for i in range(3):
            w.blit(self.spr('stone_house' if i != 1 else 'stone_door'), (60 + i * T, GROUND - T))
            w.blit(self.spr('castle_top'), (60 + i * T, GROUND - 2 * T))
        for x in (20, 330, 560):
            tree(x, 'tree_pine')
        house(420, 'roof_red', 'roof_red_top')
        house(760, 'roof_blue', 'roof_blue_top')
        w.blit(self.spr('anvil'), (1070, GROUND - T))
        house(1150, 'roof_red', 'roof_red_top', 2)
        w.blit(self.spr('well'), (1530, GROUND - T))
        house(1760, 'roof_blue', 'roof_blue_top', 2)
        house(2060, 'roof_red', 'roof_red_top')
        for x, k in [(700, 'tree'), (1110, 'bush'), (1480, 'tree_autumn'), (1700, 'tree'), (2010, 'bush'), (2290, 'tree_pine')]:
            tree(x, k)
        # cercas do vilarejo
        for x in range(2400, GATE_X, T):
            w.blit(self.spr('fence'), (x, GROUND - T))
        # placa e arredores (planície vazia)
        w.blit(self.spr('sign'), (2620, GROUND - T))
        for x in range(2700, WORLD_W, 230):
            if rnd.random() < 0.6:
                tree(x + rnd.randint(-40, 40), rnd.choice(['tree_pine', 'bush', 'mushroom']))
        w.blit(self.spr('tomb'), (MARKER_X, GROUND - T))
        # montanhas ao fundo (camada de paralaxe, mais lenta)
        self.hills = []
        h = 6
        for i in range(0, WORLD_W // 2 + W, CELL):
            h = max(3, min(9, h + rnd.choice([-1, 0, 0, 1])))
            self.hills.append(h)
        self.world = self.world.convert_alpha()

    # ------------------------------------------------------------- fluxo
    def to_free(self):
        self.state = 'free'

    def talk(self, npc):
        audio.sfx('ui_select')
        if npc is self.captain:
            if not self.quest:
                self.dialog = Dialog(self.assets, MISSAO_ACEITA, self.accept_quest)
            else:
                self.dialog = Dialog(self.assets, [(npc.name, npc.spr, 'A porteira está aberta, Sir Lineu. '
                                                                       'Os arredores ficam a leste. Vá!')], self.to_free)
        else:
            line = npc.lines[npc.talk_i % len(npc.lines)]
            npc.talk_i += 1
            npc.dir = -1 if self.kx < npc.x else 1
            self.dialog = Dialog(self.assets, [(npc.name, npc.spr, line)], self.to_free)
        self.state = 'talk'

    def accept_quest(self):
        self.quest = True
        self.state = 'free'
        audio.get().ok_jingle()
        audio.sfx('creak')
        audio.sfx('chain')

    def start_doubt(self):
        self.state = 'talk'
        self.dialog = Dialog(self.assets, DUVIDA, self.to_free)

    def start_volumar(self):
        self.state = 'volumar'
        self.volumar_t = 0.01
        audio.sfx('ui_glitch')
        audio.sfx('portal_whoosh', 0.6)
        self.dialog = Dialog(self.assets, VOLUMAR, self.done)

    def done(self):
        self.game.goto_phase(0)

    # ------------------------------------------------------------- eventos
    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.game.goto_menu()
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_F9:
            self.done()
            return
        if self.dialog and self.dialog.active:
            self.dialog.handle(e)
            return
        if self.state != 'free':
            return
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_e, pygame.K_RETURN) and self.near is not None:
                self.talk(self.near)
            elif e.key in (pygame.K_UP, pygame.K_w, pygame.K_SPACE) and self.on_ground:
                self.vy = -640
                self.on_ground = False
                audio.sfx('phase_jump', 0.5)

    def update(self, dt):
        self.t += dt
        if self.dialog:
            self.dialog.update(dt)
            if self.state == 'volumar' and self.dialog.active:
                i = self.dialog.i
                if i != getattr(self, '_vi', -1):
                    self._vi = i
                    if i == 2:
                        audio.sfx('portal_open')
                        audio.sfx('magic_chime')
        frozen = self.state != 'free'
        for n in self.npcs:
            n.update(dt, frozen and self.state != 'opening')
        if self.volumar_t:
            self.volumar_t += dt
        if self.quest and self.gate_open < 1:
            self.gate_open = min(1.0, self.gate_open + dt * 0.8)
        # ------------------------- controle do cavaleiro
        k = pygame.key.get_pressed()
        move = 0
        if self.state == 'free':
            move = (k[pygame.K_RIGHT] or k[pygame.K_d]) - (k[pygame.K_LEFT] or k[pygame.K_a])
        if move:
            self.face = move
        speed = 230
        nx = self.kx + move * speed * dt
        limit_r = GATE_X - 30 if self.gate_open < 1 else WORLD_W - 60
        if nx > limit_r and move > 0 and not self.quest:
            if getattr(self, '_gate_msg', 0) <= 0:
                self.dialog = Dialog(self.assets, [('Sir Lineu', 'knight', 'A porteira está trancada. Preciso falar '
                                                                           'com o Capitão Ortogonal primeiro.')], self.to_free)
                self.state = 'talk'
                self._gate_msg = 1
        self.kx = max(40, min(limit_r, nx))
        # gravidade simples: o cavaleiro sempre volta a pisar no chão
        self.vy += 1800 * dt
        self.ky += self.vy * dt
        if self.ky >= GROUND:
            if not self.on_ground and self.vy > 300:
                audio.sfx('step_stone')
            self.ky, self.vy, self.on_ground = float(GROUND), 0.0, True
        self.walking = bool(move) and self.on_ground
        if self.walking:
            self.step_t -= dt
            if self.step_t <= 0:
                audio.sfx('step_stone')
                self.step_t = 0.3
        # câmera 2D: translação da window para seguir o jogador
        target = max(0, min(WORLD_W - W, self.kx - W * 0.4))
        self.cam += (target - self.cam) * min(1, dt * 6)
        # aldeão mais próximo para conversar
        self.near = None
        if self.state == 'free':
            best = 110
            for n in self.npcs + [self.captain]:
                d = abs(n.x - self.kx)
                if d < best:
                    best, self.near = d, n
        # gatilhos da história
        if self.state == 'free' and self.quest:
            if self.kx > DOUBT_X and not getattr(self, '_doubted', False):
                self._doubted = True
                self.start_doubt()
            elif self.kx > VOLUMAR_X and getattr(self, '_doubted', False):
                self.start_volumar()

    # ------------------------------------------------------------- desenho
    def draw(self, surf):
        surf.fill((4, 12, 6))
        cam = int(self.cam)
        # grade de pixels de fundo (acompanha a câmera para dar sensação de movimento)
        off = cam % CELL
        for x in range(-off, W, CELL):
            pygame.draw.line(surf, (9, 26, 13), (x, 0), (x, H))
        for y in range(0, H, CELL):
            pygame.draw.line(surf, (9, 26, 13), (0, y), (W, y))
        # montanhas ao fundo com paralaxe (deslocam-se à metade da velocidade)
        pc = cam // 2
        start = pc // CELL
        for i in range(W // CELL + 2):
            idx = start + i
            if idx >= len(self.hills):
                break
            x = idx * CELL - pc
            hh = self.hills[idx]
            for r in range(hh):
                y = GROUND - 150 - r * CELL
                pygame.draw.rect(surf, (8, 26, 12) if r < hh - 1 else (16, 48, 22), (x + 1, y + 1, CELL - 2, CELL - 2))
        surf.blit(self.world, (-cam, 0))
        # porteira (abre deslizando para baixo)
        gx = GATE_X - cam
        gh = int(128 * (1 - self.gate_open))
        if gh > 0:
            for y in range(GROUND - gh, GROUND, CELL):
                pygame.draw.rect(surf, GREEN, (gx - 8, y + 1, 16, CELL - 2), 2)
        text(surf, 'ARREDORES ->', (2620 - cam + 32, GROUND - 92), 10, GREEN, kind='pixel', center=True, shadow=False)
        text(surf, 'MARCO DA BORDA', (MARKER_X - cam + 32, GROUND - 92), 10, GREEN, kind='pixel', center=True, shadow=False)
        # aldeões
        for n in self.npcs + [self.captain]:
            img = self.spr(n.spr, 4, flip=n.dir < 0)
            bob = abs(math.sin(self.t * (14 if n.spr == 'slime' else 9))) * (8 if n.spr == 'slime' else 3) if n.walking else 0
            surf.blit(img, img.get_rect(midbottom=(n.x - cam, GROUND - bob)))
        if self.near is not None and not (self.dialog and self.dialog.active):
            nx = self.near.x - cam
            r = pygame.Rect(0, 0, 150, 26)
            r.midbottom = (nx, GROUND - 76)
            pygame.draw.rect(surf, (4, 20, 8), r, border_radius=5)
            pygame.draw.rect(surf, GREEN, r, 1, border_radius=5)
            text(surf, '[E] Conversar', r.center, 10, GREEN, kind='pixel', center=True, shadow=False)
            text(surf, self.near.name, (nx, GROUND - 112), 10, (160, 230, 170), kind='pixel', center=True, shadow=False)
        # Sir Lineu (sempre com os pés no chão)
        img = self.spr('knight', 4, flip=self.face < 0)
        bob = abs(math.sin(self.t * 11)) * 3 if self.walking else 0
        surf.blit(img, img.get_rect(midbottom=(self.kx - cam, self.ky - bob)))
        if self.state == 'talk' and getattr(self, '_doubted', False) and not self.volumar_t:
            text(surf, '?', (self.kx - cam + 22, self.ky - 96 + 4 * math.sin(self.t * 4)), 26, GREEN, kind='pixel', shadow=False)
        # Volumar surge colorido (a primeira cor que Planícia já viu)
        if self.volumar_t:
            a = min(1.0, self.volumar_t / 4)
            wimg = self.assets.sprite('wizard', 5, flip=True)
            wx = self.kx - cam + 260
            wy = 300 + 10 * math.sin(self.t * 2)
            speaker = self.dialog.lines[min(self.dialog.i, len(self.dialog.lines) - 1)][0] if self.dialog else ''
            vis = 0.25 if speaker == '???' else 1.0
            for i in range(0, wimg.get_height(), 4):
                jitter = int(random.uniform(-6, 6) * (1 - a) * 3)
                strip = wimg.subsurface((0, i, wimg.get_width(), 4)).copy()
                strip.set_alpha(int(255 * vis))
                surf.blit(strip, (wx + jitter, wy + i))
            for rr in range(3):
                pygame.draw.circle(surf, (120 + rr * 40, 60, 200), (int(wx + 40), int(wy + 40)),
                                   60 + rr * 14 + int(6 * math.sin(self.t * 4 + rr)), 1)
        # HUD
        text(surf, 'Reino de Planícia', (W // 2, 30), 18, GREEN, kind='pixel', center=True)
        if self.state in ('free', 'talk') and not self.volumar_t:
            goal = 'Fale com o Capitão Ortogonal (porteira leste)' if not self.quest else \
                'Patrulhe os arredores a leste até o Marco da Borda'
            r = pygame.Rect(16, 56, 560, 54)
            pygame.draw.rect(surf, (4, 20, 8), r, border_radius=6)
            pygame.draw.rect(surf, G_MID, r, 2, border_radius=6)
            text(surf, 'MISSÃO', (r.x + 12, r.y + 8), 10, GREEN, kind='pixel', shadow=False)
            text(surf, goal, (r.x + 12, r.y + 26), 18, (190, 255, 200), kind='mono', shadow=False)
            text(surf, 'SETAS: andar   ESPAÇO: pular   E: conversar   F9: pular prólogo', (W - 16, 64), 15,
                 (120, 200, 135), kind='mono', right=True, shadow=False)
        if self.dialog and self.dialog.active:
            self.dialog.draw(surf)
