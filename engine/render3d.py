"""
render3d.py - Um pipeline gráfico 3D em software, escrito do zero.

    Vértice (SRO/objeto)
        --[ Model ]-->        SRU (mundo)
        --[ View  (lookAt) ]-->   espaço da câmera
        --[ recorte no plano near ]
        --[ Projection (perspectiva) ]--> espaço de recorte -> divisão por w -> SRN/NDC
        --[ Viewport ]-->     SRD (pixels da tela)

Visibilidade: back-face culling + algoritmo do pintor (ordenação por profundidade).
Iluminação: sombreamento constante (flat) com o modelo de Lambert + névoa.
"""
import math
import numpy as np
import pygame

from .cg import look_at, perspective, normalize


class Renderer3D:
    def __init__(self, rect, fov=60.0, near=0.1, far=300.0):
        self.rect = pygame.Rect(rect)
        self.fov = fov
        self.near = near
        self.far = far
        self.light = normalize((0.4, 1.0, 0.3))
        self.ambient = 0.35
        self.fog_color = (150, 170, 200)
        self.fog_start, self.fog_end = 25.0, 80.0
        self.V = np.eye(4)
        self.eye = np.zeros(3)
        self.P = perspective(fov, self.rect.w / self.rect.h, near, far)
        self.items = []
        self.stats = {'faces': 0, 'drawn': 0}

    # ------------------------------------------------------------ câmera
    def set_camera(self, eye, center, up=(0, 1, 0)):
        self.eye = np.asarray(eye, dtype=float)
        self.V = look_at(eye, center, up)

    def set_fov(self, fov):
        self.fov = fov
        self.P = perspective(fov, self.rect.w / self.rect.h, self.near, self.far)

    def begin(self):
        self.items = []
        self.stats = {'faces': 0, 'drawn': 0}

    # ----------------------------------------------------- transformações
    def _to_screen(self, pv):
        """pv: array (N,3) no espaço da câmera -> pixels (N,2) usando a
        matriz de projeção + divisão perspectiva + transformação de viewport."""
        N = len(pv)
        h = np.hstack([pv, np.ones((N, 1))]) @ self.P.T     # espaço de recorte
        w = h[:, 3:4]
        ndc = h[:, :2] / w                                   # SRN [-1, 1]
        sx = self.rect.x + (ndc[:, 0] + 1) * 0.5 * self.rect.w
        sy = self.rect.y + (1 - (ndc[:, 1] + 1) * 0.5) * self.rect.h   # Y invertido
        return np.stack([sx, sy], axis=1)

    def _clip_near(self, poly):
        """Sutherland-Hodgman contra o plano z = -near (espaço da câmera)."""
        zc = -self.near
        out = []
        n = len(poly)
        for i in range(n):
            a = poly[i]
            b = poly[(i + 1) % n]
            ina = a[2] <= zc
            inb = b[2] <= zc
            if ina:
                out.append(a)
            if ina != inb:
                t = (zc - a[2]) / (b[2] - a[2])
                out.append(a + (b - a) * t)
        return out

    def _shade(self, color, n_world, depth, light=True):
        if light:
            k = self.ambient + (1 - self.ambient) * max(0.0, float(n_world @ self.light))
        else:
            k = 1.0
        c = [min(255, v * k) for v in color]
        f = (depth - self.fog_start) / (self.fog_end - self.fog_start)
        f = max(0.0, min(0.85, f))
        return tuple(int(c[i] * (1 - f) + self.fog_color[i] * f) for i in range(3))

    # ---------------------------------------------------------- primitivas
    _group_cache = {}

    def _groups(self, faces):
        key = id(faces)
        hit = self._group_cache.get(key)
        if hit is not None and hit[0] is faces:
            return hit[1]
        groups = {}
        for fi, f in enumerate(faces):
            groups.setdefault(len(f), []).append(fi)
        out = [(k, np.array(fis), np.array([faces[i] for i in fis])) for k, fis in groups.items()]
        if len(self._group_cache) > 300:
            self._group_cache.clear()
        self._group_cache[key] = (faces, out)
        return out

    def mesh(self, verts, faces, model, color, light=True, cull=True, outline=None, layer=1, colors=None):
        """Desenha uma malha poligonal. Normais, culling, iluminação e névoa são
        calculados de forma vetorizada (numpy) para todas as faces de uma vez."""
        verts = np.asarray(verts, dtype=float)
        vw = verts @ model[:3, :3].T + model[:3, 3]                 # SRO -> SRU (mundo)
        vc = vw @ self.V[:3, :3].T + self.V[:3, 3]                  # SRU -> câmera
        zc = -self.near
        # rejeição rápida pela esfera envolvente (atrás da câmera / fora do frustum)
        cen = vc.mean(axis=0)
        rad = float(np.sqrt(((vc - cen) ** 2).sum(axis=1)).max())
        if cen[2] - rad > zc:
            return
        tf = math.tan(math.radians(self.fov) / 2)
        aspect = self.rect.w / self.rect.h
        if -cen[2] > rad and (abs(cen[0]) - rad > -cen[2] * tf * aspect * 1.05 or abs(cen[1]) - rad > -cen[2] * tf * 1.05):
            return
        with np.errstate(all='ignore'):
            scr = self._to_screen(vc)
        for k, fis, F in self._groups(faces):
            self.stats['faces'] += len(fis)
            Pw = vw[F]
            Pc = vc[F]
            if k == 3:
                n = np.cross(Pw[:, 1] - Pw[:, 0], Pw[:, 2] - Pw[:, 0])
            else:
                n = np.cross(Pw[:, 2] - Pw[:, 0], Pw[:, 3] - Pw[:, 1])
            ln = np.linalg.norm(n, axis=1)
            valid = ln > 1e-12
            n = n / np.where(valid, ln, 1)[:, None]
            centers = Pw.mean(axis=1)
            facing = ((self.eye - centers) * n).sum(axis=1)
            zmin = Pc[:, :, 2].min(axis=1)
            zmax = Pc[:, :, 2].max(axis=1)
            keep = valid & (zmin <= zc)
            if cull:
                keep &= facing > 0                                  # back-face culling
            else:
                n = np.where((facing < 0)[:, None], -n, n)          # iluminação dos dois lados
            depth = -Pc[:, :, 2].mean(axis=1)
            if light:
                kl = self.ambient + (1 - self.ambient) * np.clip(n @ self.light, 0, 1)
            else:
                kl = np.ones(len(fis))
            fog = np.clip((depth - self.fog_start) / (self.fog_end - self.fog_start), 0, 0.85)
            for j in np.nonzero(keep)[0]:
                col = colors[fis[j]] if colors is not None else color
                f = fog[j]
                c = tuple(int(min(255, col[i] * kl[j]) * (1 - f) + self.fog_color[i] * f) for i in range(3))
                if zmax[j] > zc:
                    poly = self._clip_near(list(Pc[j]))
                    if len(poly) < 3:
                        continue
                    pts = self._to_screen(np.array(poly))
                else:
                    pts = scr[F[j]]
                self.items.append((layer, float(depth[j]), 'poly', pts.tolist(), c, outline))

    def billboard(self, pos, image_fn, height, layer=1, flip=False):
        """Sprite 2D sempre voltado para a câmera (billboard)."""
        p = np.append(np.asarray(pos, dtype=float), 1.0) @ self.V.T
        if p[2] > -self.near:
            return None
        depth = -p[2]
        s = self._to_screen(p[None, :3])[0]
        f = 1 / math.tan(math.radians(self.fov) / 2)
        px = height * f * (self.rect.h / 2) / depth
        if px < 2 or px > 3000:
            return None
        self.items.append((layer, depth, 'bb', (s[0], s[1]), image_fn, int(px), flip))
        return (s[0], s[1], px)

    def sphere(self, pos, radius, color, layer=1, glow=True):
        p = np.append(np.asarray(pos, dtype=float), 1.0) @ self.V.T
        if p[2] > -self.near:
            return
        depth = -p[2]
        s = self._to_screen(p[None, :3])[0]
        f = 1 / math.tan(math.radians(self.fov) / 2)
        px = radius * f * (self.rect.h / 2) / depth
        if px < 0.5 or px > 2000:
            return
        self.items.append((layer, depth, 'sph', (s[0], s[1]), px, color, glow))

    def line(self, a, b, color, width=1, layer=1):
        pa = np.append(np.asarray(a, dtype=float), 1.0) @ self.V.T
        pb = np.append(np.asarray(b, dtype=float), 1.0) @ self.V.T
        poly = [pa[:3], pb[:3]]
        zc = -self.near
        if pa[2] > zc and pb[2] > zc:
            return
        if pa[2] > zc or pb[2] > zc:
            t = (zc - pa[2]) / (pb[2] - pa[2])
            m = pa[:3] + (pb[:3] - pa[:3]) * t
            poly = [m, pb[:3]] if pa[2] > zc else [pa[:3], m]
        s = self._to_screen(np.array(poly))
        depth = float(-(poly[0][2] + poly[1][2]) / 2)
        self.items.append((layer, depth, 'line', (tuple(s[0]), tuple(s[1])), color, width))

    # --------------------------------------------------------- desenho
    def render(self, surf):
        clip = surf.get_clip()
        surf.set_clip(self.rect)
        # algoritmo do pintor: camada, depois do mais distante ao mais próximo
        self.items.sort(key=lambda it: (it[0], -it[1]))
        for it in self.items:
            kind = it[2]
            if kind == 'poly':
                pts, col, outline = it[3], it[4], it[5]
                try:
                    pygame.draw.polygon(surf, col, pts)
                    if outline:
                        pygame.draw.polygon(surf, outline, pts, 1)
                except (TypeError, ValueError):
                    pass
                self.stats['drawn'] += 1
            elif kind == 'bb':
                (x, y), fn, px, flip = it[3], it[4], it[5], it[6]
                img = fn(px, flip)
                r = img.get_rect(midbottom=(x, y + px * 0.5))
                surf.blit(img, r)
            elif kind == 'sph':
                (x, y), px, col, glow = it[3], it[4], it[5], it[6]
                if glow:
                    g = pygame.Surface((int(px * 6) + 2, int(px * 6) + 2), pygame.SRCALPHA)
                    pygame.draw.circle(g, col + (70,), g.get_rect().center, int(px * 3))
                    surf.blit(g, g.get_rect(center=(x, y)))
                pygame.draw.circle(surf, col, (int(x), int(y)), max(1, int(px)))
                pygame.draw.circle(surf, (255, 255, 230), (int(x), int(y)), max(1, int(px * 0.5)))
            elif kind == 'line':
                a, b = it[3]
                pygame.draw.line(surf, it[4], a, b, it[5])
        surf.set_clip(clip)
