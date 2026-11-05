"""Widgets de interface com visual medieval (pergaminho / pedra / ouro)."""
import math
import pygame
from .assets import font, text, wrap
from . import audio

C = {
    'bg': (18, 16, 28),
    'panel': (34, 28, 44),
    'panel2': (52, 42, 60),
    'border': (196, 160, 82),
    'border_dark': (110, 84, 40),
    'text': (238, 228, 204),
    'dim': (150, 140, 125),
    'gold': (246, 204, 92),
    'red': (226, 78, 64),
    'green': (104, 206, 120),
    'blue': (96, 156, 236),
    'purple': (170, 110, 230),
    'parch': (226, 206, 160),
    'ink': (60, 40, 24),
}


def panel(surf, rect, alpha=230, border=None, fill=None, radius=10):
    rect = pygame.Rect(rect)
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (fill or C['panel']) + (alpha,), s.get_rect(), border_radius=radius)
    surf.blit(s, rect.topleft)
    pygame.draw.rect(surf, C['border_dark'], rect, 4, border_radius=radius)
    pygame.draw.rect(surf, border or C['border'], rect.inflate(-4, -4), 2, border_radius=radius)
    # rebites nos cantos
    for cx, cy in (rect.topleft, rect.topright, rect.bottomleft, rect.bottomright):
        dx = 8 if cx == rect.left else -8
        dy = 8 if cy == rect.top else -8
        pygame.draw.circle(surf, C['gold'], (cx + dx, cy + dy), 3)


def parchment(surf, rect):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, C['parch'], rect, border_radius=6)
    pygame.draw.rect(surf, (180, 150, 100), rect, 3, border_radius=6)
    for i in range(0, rect.h, 7):
        pygame.draw.line(surf, (214, 192, 146), (rect.x + 6, rect.y + i), (rect.right - 6, rect.y + i))


class Button:
    def __init__(self, rect, label, cb=None, size=22, hotkey=None, color=None, enabled=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.cb = cb
        self.size = size
        self.hotkey = hotkey
        self.color = color
        self.enabled = enabled
        self.hover = False
        self.selected = False

    def handle(self, e):
        if not self.enabled:
            return False
        if e.type == pygame.MOUSEMOTION:
            h = self.rect.collidepoint(e.pos)
            if h and not self.hover:
                audio.sfx('ui_hover')
            self.hover = h
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            audio.sfx('ui_click')
            if self.cb:
                self.cb()
            return True
        elif e.type == pygame.KEYDOWN and self.hotkey is not None and e.key == self.hotkey:
            audio.sfx('ui_click')
            if self.cb:
                self.cb()
            return True
        return False

    def draw(self, surf):
        base = self.color or (70, 54, 40)
        if not self.enabled:
            base = (50, 46, 46)
        elif self.selected:
            base = (130, 96, 40)
        elif self.hover:
            base = tuple(min(255, c + 30) for c in base)
        pygame.draw.rect(surf, (20, 14, 10), self.rect.move(0, 3), border_radius=8)
        pygame.draw.rect(surf, base, self.rect, border_radius=8)
        pygame.draw.rect(surf, C['gold'] if (self.hover or self.selected) and self.enabled else C['border_dark'],
                         self.rect, 2, border_radius=8)
        col = C['text'] if self.enabled else C['dim']
        text(surf, self.label, self.rect.center, self.size, col, center=True)


class Slider:
    def __init__(self, rect, label, vmin, vmax, value, step=1, fmt='{:.0f}', color=None, on_change=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.vmin, self.vmax, self.step = vmin, vmax, step
        self.value = value
        self.fmt = fmt
        self.color = color or C['gold']
        self.drag = False
        self.on_change = on_change

    def _set_from_x(self, x):
        t = (x - self.rect.x) / self.rect.w
        t = max(0.0, min(1.0, t))
        v = self.vmin + t * (self.vmax - self.vmin)
        v = round(v / self.step) * self.step
        v = max(self.vmin, min(self.vmax, v))
        if abs(v - self.value) > 1e-9:
            self.value = v
            audio.sfx('ui_scroll')
            if self.on_change:
                self.on_change(v)

    def handle(self, e):
        hit = self.rect.inflate(16, 24)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and hit.collidepoint(e.pos):
            self.drag = True
            self._set_from_x(e.pos[0])
            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.drag = False
        if e.type == pygame.MOUSEMOTION and self.drag:
            self._set_from_x(e.pos[0])
            return True
        if e.type == pygame.MOUSEWHEEL and hit.collidepoint(pygame.mouse.get_pos()):
            v = max(self.vmin, min(self.vmax, self.value + e.y * self.step))
            if v != self.value:
                self.value = v
                audio.sfx('ui_scroll')
                if self.on_change:
                    self.on_change(v)
            return True
        return False

    def draw(self, surf):
        text(surf, self.label, (self.rect.x, self.rect.y - 26), 18, C['text'])
        text(surf, self.fmt.format(self.value), (self.rect.right, self.rect.y - 26), 18, self.color, kind='mono', right=True)
        pygame.draw.rect(surf, (20, 16, 20), self.rect, border_radius=5)
        t = (self.value - self.vmin) / (self.vmax - self.vmin) if self.vmax != self.vmin else 0
        fill = self.rect.copy()
        fill.w = int(self.rect.w * t)
        pygame.draw.rect(surf, self.color, fill, border_radius=5)
        pygame.draw.rect(surf, C['border_dark'], self.rect, 2, border_radius=5)
        kx = self.rect.x + int(self.rect.w * t)
        pygame.draw.circle(surf, (30, 20, 10), (kx, self.rect.centery), 11)
        pygame.draw.circle(surf, C['gold'], (kx, self.rect.centery), 9)


class TextInput:
    def __init__(self, rect, label, numeric=True, maxlen=8):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.value = ''
        self.active = False
        self.numeric = numeric
        self.maxlen = maxlen

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            was = self.active
            self.active = self.rect.collidepoint(e.pos)
            if self.active and not was:
                audio.sfx('ui_select')
            return self.active
        if e.type == pygame.KEYDOWN and self.active:
            audio.sfx('ui_type')
            if e.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
            elif e.unicode and len(self.value) < self.maxlen:
                ch = e.unicode.replace(',', '.')
                if not self.numeric or ch in '0123456789.-':
                    self.value += ch
            return True
        return False

    def number(self):
        try:
            return float(self.value)
        except ValueError:
            return None

    def draw(self, surf):
        text(surf, self.label, (self.rect.x, self.rect.y - 24), 18)
        pygame.draw.rect(surf, (16, 12, 16), self.rect, border_radius=6)
        pygame.draw.rect(surf, C['gold'] if self.active else C['border_dark'], self.rect, 2, border_radius=6)
        cursor = '|' if self.active and (pygame.time.get_ticks() // 400) % 2 == 0 else ''
        text(surf, self.value + cursor, (self.rect.x + 10, self.rect.y + 6), 22, C['text'], kind='mono', shadow=False)


class Dialog:
    """Caixa de diálogo com efeito máquina de escrever e retrato."""

    def __init__(self, assets, lines, on_done=None):
        self.assets = assets
        self.lines = lines          # lista de (nome, sprite_key|None, texto)
        self.i = 0
        self.chars = 0.0
        self.on_done = on_done
        self.active = True
        self.speed = 55
        self._voice()

    def _cur(self):
        return self.lines[self.i]

    def _voice(self):
        """Som característico quando um personagem começa a falar."""
        if self.i >= len(self.lines):
            return
        spr = self.lines[self.i][1]
        if spr == 'dragon':
            audio.sfx('growl')
        elif spr == 'wizard':
            audio.sfx('ui_pluck', 0.6)

    def handle(self, e):
        adv = (e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)) or \
              (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1)
        if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
            audio.sfx('page')
            self.i = len(self.lines) - 1
            self.chars = 1e9
            return True
        if adv:
            full = len(self._cur()[2])
            if self.chars < full:
                self.chars = full
            else:
                self.i += 1
                self.chars = 0
                audio.sfx('page')
                self._voice()
                if self.i >= len(self.lines):
                    self.active = False
                    if self.on_done:
                        self.on_done()
            return True
        return False

    def update(self, dt):
        if self.active:
            before = int(self.chars)
            self.chars += self.speed * dt
            if before < len(self._cur()[2]) and int(self.chars) // 3 > before // 3:
                audio.sfx('ui_type')

    def draw(self, surf):
        if not self.active:
            return
        name, spr, msg = self._cur()
        W, H = surf.get_size()
        rect = pygame.Rect(40, H - 200, W - 80, 180)
        panel(surf, rect, alpha=240)
        x = rect.x + 24
        if spr:
            frame = pygame.Rect(rect.x + 20, rect.y + 24, 120, 120)
            pygame.draw.rect(surf, (20, 16, 24), frame, border_radius=8)
            pygame.draw.rect(surf, C['border'], frame, 2, border_radius=8)
            if spr == 'dragon':
                img = self.assets.dragon_img(100)
                img = img.subsurface((0, 0, min(img.get_width(), 110), 100))
                surf.blit(img, (frame.x + 5, frame.y + 10))
            else:
                img = self.assets.sprite(spr, 6)
                surf.blit(img, img.get_rect(center=frame.center))
            x = frame.right + 24
        text(surf, name, (x, rect.y + 18), 26, C['gold'])
        shown = msg[:int(self.chars)]
        f = font(22)
        y = rect.y + 56
        for line in wrap(shown, f, rect.right - x - 30):
            text(surf, line, (x, y), 22, C['text'], shadow=False)
            y += f.get_linesize() + 2
        if self.chars >= len(msg) and (pygame.time.get_ticks() // 350) % 2 == 0:
            pygame.draw.polygon(surf, C['gold'], [(rect.right - 40, rect.bottom - 30), (rect.right - 24, rect.bottom - 30),
                                                  (rect.right - 32, rect.bottom - 20)])
        text(surf, 'ESPAÇO/clique: avançar   TAB: pular', (rect.right - 20, rect.bottom - 26), 14, C['dim'], right=True, shadow=False)


def draw_arrow(surf, color, a, b, width=2, head=10):
    pygame.draw.line(surf, color, a, b, width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for s in (-1, 1):
        p = (b[0] - head * math.cos(ang + s * 0.45), b[1] - head * math.sin(ang + s * 0.45))
        pygame.draw.line(surf, color, b, p, width)


def dashed_line(surf, color, a, b, width=1, dash=8):
    x0, y0 = a
    x1, y1 = b
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1:
        return
    n = int(L // dash)
    for i in range(0, n, 2):
        t0, t1 = i / n, min(1, (i + 1) / n)
        pygame.draw.line(surf, color, (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0),
                         (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1), width)


def dashed_poly(surf, color, pts, width=2, dash=8, closed=True):
    n = len(pts)
    for i in range(n if closed else n - 1):
        dashed_line(surf, color, pts[i], pts[(i + 1) % n], width, dash)


def matrix_view(surf, M, pos, size=18, title=None, color=None, fmt='{:6.2f}'):
    x, y = pos
    if title:
        text(surf, title, (x, y), 18, C['gold'])
        y += 26
    f = font(size, 'mono')
    rows = [' '.join(fmt.format(v + 0.0) for v in row) for row in M]
    w = max(f.size(r)[0] for r in rows) + 20
    h = len(rows) * (f.get_linesize()) + 8
    col = color or C['text']
    pygame.draw.lines(surf, col, False, [(x + 8, y), (x, y), (x, y + h), (x + 8, y + h)], 2)
    pygame.draw.lines(surf, col, False, [(x + w - 8, y), (x + w, y), (x + w, y + h), (x + w - 8, y + h)], 2)
    for i, r in enumerate(rows):
        text(surf, r, (x + 10, y + 4 + i * f.get_linesize()), size, col, kind='mono', shadow=False)
    return pygame.Rect(x, pos[1], w, y + h - pos[1])
