"""Montagem de cenários 2D a partir dos tiles (vilarejo, floresta, castelo)."""
import math
import random
import pygame
import numpy as np


def gradient(surf, rect, top, bottom):
    x, y, w, h = rect
    for i in range(h):
        t = i / max(1, h - 1)
        c = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3))
        pygame.draw.line(surf, c, (x, y + i), (x + w, y + i))


def hills(surf, assets, y, idx=(14, 15), fill=22, scale=4, height=None):
    s = 24 * scale
    for i, x in enumerate(range(0, surf.get_width(), s)):
        surf.blit(assets.background(idx[i % len(idx)], scale), (x, y))
    if height:
        for x in range(0, surf.get_width(), s):
            for yy in range(y + s, y + height, s):
                surf.blit(assets.background(fill, scale), (x, yy))


def ground(surf, assets, y, rows=2, scale=3, top='grass', fill='grass2', rnd=None):
    rnd = rnd or random.Random(1)
    s = 16 * scale
    for r in range(rows):
        for x in range(0, surf.get_width(), s):
            name = top if r == 0 else fill
            if r == 0 and rnd.random() < 0.15:
                name = 'grass_flower'
            surf.blit(assets.sprite(name, scale), (x, y + r * s))


def house(surf, assets, x, y, roof='red', w=3, scale=3):
    """Casa com telhado: (x,y) = canto inferior esquerdo."""
    s = 16 * scale
    roof_n = 'roof_red' if roof == 'red' else 'roof_blue'
    top_n = 'roof_red_top' if roof == 'red' else 'roof_blue_top'
    for i in range(w):
        name = 'house_door' if i == w // 2 else 'house_win'
        surf.blit(assets.sprite(name, scale), (x + i * s, y - s))
        surf.blit(assets.sprite(roof_n, scale), (x + i * s, y - 2 * s))
    surf.blit(assets.sprite(top_n, scale), (x + (w // 2) * s, y - 3 * s))


def tree(surf, assets, x, y, kind='tree', scale=3):
    img = assets.sprite(kind, scale)
    surf.blit(img, img.get_rect(midbottom=(x, y)))


def castle(surf, assets, x, y, w=6, h=4, scale=3, gate=True):
    s = 16 * scale
    for i in range(w):
        for j in range(h):
            surf.blit(assets.sprite('castle_wall', scale), (x + i * s, y - (j + 1) * s))
        surf.blit(assets.sprite('castle_top', scale), (x + i * s, y - (h + 1) * s))
    if gate:
        g = w // 2 - 1
        surf.blit(assets.sprite('castle_gate', scale), (x + g * s, y - s))
        surf.blit(assets.sprite('castle_gate2', scale), (x + (g + 1) * s, y - s))


def grayscale(surface):
    """Converte para tons de cinza usando a luminância (0.299R+0.587G+0.114B)."""
    arr = pygame.surfarray.array3d(surface).astype(np.float32)
    lum = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114
    g = np.repeat(lum[..., None], 3, axis=2).astype(np.uint8)
    out = pygame.Surface(surface.get_size())
    pygame.surfarray.blit_array(out, g)
    return out


def water(surf, rect, t, base=(40, 90, 170)):
    pygame.draw.rect(surf, base, rect)
    x, y, w, h = rect
    for j in range(0, h, 10):
        for i in range(0, w, 30):
            ox = int(6 * math.sin(t * 2 + j * 0.3 + i * 0.1))
            pygame.draw.line(surf, (min(255, base[0] + 60), min(255, base[1] + 60), min(255, base[2] + 50)),
                             (x + i + ox, y + j + 4), (x + i + ox + 12, y + j + 4), 2)
