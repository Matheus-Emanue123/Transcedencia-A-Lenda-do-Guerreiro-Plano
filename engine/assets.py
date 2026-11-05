"""Carregamento de sprites, fontes e utilidades de texto."""
import os
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')

# Índices dos tiles 16x16 nos pacotes da Kenney (CC0)
SPRITES = {
    # personagens (Tiny Dungeon)
    'knight': ('dungeon', 97),
    'knight2': ('dungeon', 96),
    'wizard': ('dungeon', 84),        # Volumar, o Arquimago Volumétrico
    'illusionist': ('dungeon', 111),
    'scout': ('dungeon', 112),
    'princess': ('dungeon', 99),
    'king': ('dungeon', 100),
    'smith': ('dungeon', 87),
    'ghost': ('dungeon', 121),
    'bat': ('dungeon', 120),
    'demon': ('dungeon', 110),
    'slime': ('dungeon', 108),
    # objetos
    'chest': ('dungeon', 89),
    'potion_r': ('dungeon', 115), 'potion_g': ('dungeon', 114), 'potion_b': ('dungeon', 116),
    'sword': ('dungeon', 104), 'staff': ('dungeon', 130), 'staff2': ('dungeon', 129),
    'shield_crest': ('dungeon', 29), 'door': ('dungeon', 46), 'door_open': ('dungeon', 9),
    'wall': ('dungeon', 40), 'wall2': ('dungeon', 57), 'floor': ('dungeon', 48),
    'floor_dark': ('dungeon', 0), 'torch_wall': ('dungeon', 41), 'stone_wall': ('dungeon', 14),
    'gate': ('dungeon', 28), 'brick': ('dungeon', 59), 'pillar': ('dungeon', 18),
    'barrel': ('dungeon', 82), 'tomb': ('dungeon', 65), 'anvil': ('dungeon', 74),
    # vilarejo (Tiny Town)
    'grass': ('town', 0), 'grass2': ('town', 1), 'grass_flower': ('town', 2),
    'tree': ('town', 16), 'tree_pine': ('town', 4), 'tree_autumn': ('town', 15),
    'bush': ('town', 5), 'mushroom': ('town', 29), 'path': ('town', 25),
    'roof_red': ('town', 53), 'roof_red_top': ('town', 67), 'roof_blue': ('town', 49),
    'roof_blue_top': ('town', 63), 'house_wall': ('town', 73), 'house_door': ('town', 86),
    'house_win': ('town', 84), 'stone_house': ('town', 77), 'stone_door': ('town', 89),
    'castle_wall': ('town', 96), 'castle_top': ('town', 99), 'castle_gate': ('town', 111),
    'castle_gate2': ('town', 112), 'fence': ('town', 45), 'sign': ('town', 83),
    'well': ('town', 104), 'key': ('town', 117), 'bow': ('town', 118), 'target': ('town', 95),
    'cobble': ('town', 126), 'castle_floor': ('town', 109),
}


class Assets:
    def __init__(self):
        self.sheets = {}
        for name in ('dungeon', 'town', 'backgrounds'):
            path = os.path.join(ASSETS, 'sprites', name + '.png')
            try:
                self.sheets[name] = pygame.image.load(path).convert_alpha()
            except Exception:
                self.sheets[name] = None
        try:
            self.dragon = pygame.image.load(os.path.join(ASSETS, 'sprites', 'dragon.png')).convert_alpha()
        except Exception:
            self.dragon = self._placeholder((458, 291), (120, 40, 40))
        self._cache = {}

    @staticmethod
    def _placeholder(size, color):
        s = pygame.Surface(size, pygame.SRCALPHA)
        s.fill(color + (255,))
        return s

    def tile(self, pack, idx, scale=1):
        key = (pack, idx, scale)
        if key in self._cache:
            return self._cache[key]
        sheet = self.sheets.get(pack)
        if sheet is None:
            surf = self._placeholder((16, 16), (200, 0, 200))
        else:
            cols = sheet.get_width() // 16
            surf = sheet.subsurface(((idx % cols) * 16, (idx // cols) * 16, 16, 16)).copy()
        if scale != 1:
            surf = pygame.transform.scale(surf, (16 * scale, 16 * scale))
        self._cache[key] = surf
        return surf

    def sprite(self, name, scale=3, flip=False):
        key = ('spr', name, scale, flip)
        if key in self._cache:
            return self._cache[key]
        pack, idx = SPRITES[name]
        s = self.tile(pack, idx, scale)
        if flip:
            s = pygame.transform.flip(s, True, False)
        self._cache[key] = s
        return s

    def mono(self, name, scale, color):
        """Versão monocromática (silhueta) de um sprite - usada no mundo 2D
        primitivo da Fase 1, onde as cores ainda não existem."""
        key = ('mono', name, scale, color)
        if key in self._cache:
            return self._cache[key]
        src = self.sprite(name, scale)
        out = pygame.Surface(src.get_size(), pygame.SRCALPHA)
        w, h = src.get_size()
        # luminância quantizada em 4 tons do fósforo (como um monitor CRT monocromático)
        levels = (0.22, 0.45, 0.72, 1.0)
        for x in range(w):
            for y in range(h):
                r, g, b, a = src.get_at((x, y))
                if a > 100:
                    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    k = levels[min(3, int(lum * 4.2))]
                    out.set_at((x, y), (int(color[0] * k), int(color[1] * k), int(color[2] * k), 255))
        self._cache[key] = out
        return out

    def background(self, idx, scale=4):
        """Tiles de fundo do Pixel Platformer (céu/colinas) - 24x24."""
        key = ('bg', idx, scale)
        if key in self._cache:
            return self._cache[key]
        sheet = self.sheets.get('backgrounds')
        if sheet is None:
            s = self._placeholder((24 * scale, 24 * scale), (120, 180, 220))
        else:
            cols = sheet.get_width() // 24
            s = sheet.subsurface(((idx % cols) * 24, (idx // cols) * 24, 24, 24)).copy()
            s = pygame.transform.scale(s, (24 * scale, 24 * scale))
        self._cache[key] = s
        return s

    def dragon_img(self, height, flip=False):
        key = ('dragon', height, flip)
        if key in self._cache:
            return self._cache[key]
        w = int(self.dragon.get_width() * height / self.dragon.get_height())
        s = pygame.transform.smoothscale(self.dragon, (max(1, w), max(1, height)))
        if flip:
            s = pygame.transform.flip(s, True, False)
        if len(self._cache) > 600:
            self._cache = {k: v for k, v in self._cache.items() if k[0] != 'dragon'}
        self._cache[key] = s
        return s


# ----------------------------------------------------------------------------
# Fontes
# ----------------------------------------------------------------------------
_fonts = {}


def font(size, kind='medieval'):
    key = (size, kind)
    if key in _fonts:
        return _fonts[key]
    f = None
    try:
        if kind == 'medieval':
            f = pygame.font.Font(os.path.join(ASSETS, 'fonts', 'MedievalSharp.ttf'), size)
        elif kind == 'pixel':
            f = pygame.font.Font(os.path.join(ASSETS, 'fonts', 'PressStart2P.ttf'), size)
        elif kind == 'mono':
            f = pygame.font.SysFont('consolas,couriernew,monospace', size)
        else:
            f = pygame.font.SysFont('georgia,timesnewroman,serif', size)
    except Exception:
        f = None
    if f is None:
        f = pygame.font.Font(None, int(size * 1.3))
    _fonts[key] = f
    return f


def text(surf, s, pos, size=22, color=(235, 225, 200), kind='medieval', center=False,
         right=False, shadow=True):
    f = font(size, kind)
    img = f.render(str(s), True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
    if shadow:
        sh = f.render(str(s), True, (0, 0, 0))
        surf.blit(sh, (r.x + 2, r.y + 2))
    surf.blit(img, r)
    return r


def wrap(s, f, width):
    lines = []
    for para in str(s).split('\n'):
        words = para.split(' ')
        cur = ''
        for w in words:
            test = (cur + ' ' + w).strip()
            if f.size(test)[0] <= width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def text_block(surf, s, rect, size=20, color=(235, 225, 200), kind='medieval', spacing=4, shadow=False):
    f = font(size, kind)
    x, y, w, h = rect
    for line in wrap(s, f, w):
        if line:
            text(surf, line, (x, y), size, color, kind, shadow=shadow)
        y += f.get_linesize() + spacing
    return y
