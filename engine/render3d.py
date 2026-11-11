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

Qualidade alta (hq): luz ambiente HEMISFÉRICA (faces voltadas para o céu recebem
mais luz ambiente que as voltadas para o chão) e bordas dos polígonos suavizadas
(antisserrilhamento com linhas aa). Custa mais quadros por segundo.
"""
import math
import numpy as np
import pygame

from .cg import look_at, perspective, normalize

KEY_COLOR = (255, 0, 255)       # cor usada como transparente (colorkey) nos decalques

# Vértices atrás da câmera geram divisões por zero na projeção; essas faces são descartadas ou
# recortadas depois, então os avisos do numpy são desligados uma vez aqui (mais barato do que
# abrir um bloco np.errstate a cada malha desenhada).
np.seterr(divide='ignore', invalid='ignore', over='ignore')


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
        self.fog_max = 0.85             # névoa máxima (1 = objetos distantes somem por completo)
        self.V = np.eye(4)
        self.eye = np.zeros(3)
        self.P = perspective(fov, self.rect.w / self.rect.h, near, far)
        self.items = []
        self.stats = {'faces': 0, 'drawn': 0}
        self.hq = False

    @property
    def fog_arr(self):
        return np.array(self.fog_color, dtype=np.float32)

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
        # A matriz de perspectiva só tem P[0,0], P[1,1] e w = -z relevantes para x e y:
        # recorte -> divisão por w (SRN em [-1, 1]) -> viewport, com o Y invertido.
        P, R = self.P, self.rect
        w = -pv[:, 2]
        out = np.empty((len(pv), 2))
        out[:, 0] = R.x + (pv[:, 0] * P[0, 0] / w + 1) * (0.5 * R.w)
        out[:, 1] = R.y + (1 - pv[:, 1] * P[1, 1] / w) * (0.5 * R.h)
        return out

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

    @staticmethod
    def clip_rect(poly, x0, y0, x1, y1):
        """Sutherland-Hodgman 2D: recorta o polígono contra o retângulo da viewport.
        Evita que faces muito próximas da câmera virem polígonos com coordenadas
        gigantescas (lentos de preencher)."""
        def clip(pts, inside, inter):
            out = []
            n = len(pts)
            for i in range(n):
                a, b = pts[i], pts[(i + 1) % n]
                ia, ib = inside(a), inside(b)
                if ia:
                    out.append(a)
                if ia != ib:
                    out.append(inter(a, b))
            return out

        def ix(a, b, x):
            t = (x - a[0]) / (b[0] - a[0])
            return (x, a[1] + (b[1] - a[1]) * t)

        def iy(a, b, y):
            t = (y - a[1]) / (b[1] - a[1])
            return (a[0] + (b[0] - a[0]) * t, y)
        p = poly
        p = clip(p, lambda q: q[0] >= x0, lambda a, b: ix(a, b, x0))
        if p:
            p = clip(p, lambda q: q[0] <= x1, lambda a, b: ix(a, b, x1))
        if p:
            p = clip(p, lambda q: q[1] >= y0, lambda a, b: iy(a, b, y0))
        if p:
            p = clip(p, lambda q: q[1] <= y1, lambda a, b: iy(a, b, y1))
        return p

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
        if len(self._group_cache) > 3000:
            self._group_cache.clear()
        self._group_cache[key] = (faces, out)
        return out

    def visible(self, center, radius):
        """Teste rápido de visibilidade (frustum culling) pela esfera envolvente: leva só o centro
        ao espaço da câmera e compara com os planos do tronco de pirâmide. Quem chama evita, assim,
        transformar milhares de vértices de um objeto que nem aparece na tela."""
        V = self.V
        x, y, z = center
        cz = V[2, 0] * x + V[2, 1] * y + V[2, 2] * z + V[2, 3]
        if cz - radius > -self.near:                       # inteiro atrás da câmera
            return False
        d = -cz
        if d > radius:
            tf = math.tan(math.radians(self.fov) / 2) * 1.05
            cx = V[0, 0] * x + V[0, 1] * y + V[0, 2] * z + V[0, 3]
            if abs(cx) - radius > d * tf * self.rect.w / self.rect.h:
                return False
            cy = V[1, 0] * x + V[1, 1] * y + V[1, 2] * z + V[1, 3]
            if abs(cy) - radius > d * tf:
                return False
        return True

    def mesh(self, verts, faces, model, color, light=True, cull=True, outline=None, layer=1, colors=None,
             fogk=1.0):
        """Desenha uma malha poligonal. Normais, culling, iluminação e névoa são
        calculados de forma vetorizada (numpy) para todas as faces de uma vez.
        model=None indica vértices já no SRU (geometria estática): pula a transformação de modelo."""
        verts = np.asarray(verts, dtype=float)
        vw = verts if model is None else verts @ model[:3, :3].T + model[:3, 3]     # SRO -> SRU (mundo)
        vc = vw @ self.V[:3, :3].T + self.V[:3, 3]                  # SRU -> câmera
        zc = -self.near
        # rejeição rápida pela esfera envolvente (atrás da câmera / fora do frustum)
        cen = vc.mean(axis=0)
        dv = vc - cen
        rad = math.sqrt(float((dv * dv).sum(axis=1).max()))
        if cen[2] - rad > zc:
            return
        tf = math.tan(math.radians(self.fov) / 2)
        aspect = self.rect.w / self.rect.h
        if -cen[2] > rad and (abs(cen[0]) - rad > -cen[2] * tf * aspect * 1.05 or abs(cen[1]) - rad > -cen[2] * tf * 1.05):
            return
        scr = self._to_screen(vc)
        vz = vc[:, 2]
        eye = self.eye
        R_ = self.rect
        for k, fis, F in self._groups(faces):
            self.stats['faces'] += len(fis)
            # normal da face pelo produto vetorial de duas arestas (triângulo) ou das diagonais (quadrilátero)
            P0 = vw[F[:, 0]]
            if k == 3:
                a, b = vw[F[:, 1]] - P0, vw[F[:, 2]] - P0
            else:
                a, b = vw[F[:, 2]] - P0, vw[F[:, 3]] - vw[F[:, 1]]
            n = np.empty_like(a)
            n[:, 0] = a[:, 1] * b[:, 2] - a[:, 2] * b[:, 1]
            n[:, 1] = a[:, 2] * b[:, 0] - a[:, 0] * b[:, 2]
            n[:, 2] = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
            ln = np.sqrt((n * n).sum(axis=1))
            facing = ((eye - P0) * n).sum(axis=1)                   # > 0: a face olha para a câmera
            Z = vz[F]
            zmin, zmax = Z.min(axis=1), Z.max(axis=1)
            keep = (ln > 1e-12) & (zmin <= zc)
            if cull:
                keep &= facing > 0                                  # back-face culling
            idx = np.nonzero(keep)[0]
            if len(idx) == 0:
                continue
            # daqui em diante só as faces que sobraram
            Fk = F[idx]
            P2 = scr[Fk]
            zmax = zmax[idx]
            sx, sy = P2[:, :, 0], P2[:, :, 1]
            nxt = list(range(1, k)) + [0]
            area = 0.5 * np.abs((sx * sy[:, nxt] - sy * sx[:, nxt]).sum(axis=1))   # área projetada (cadarço)
            big_enough = ~((zmax <= zc) & (area < 1.0))             # descarta faces menores que ~1 pixel²
            if not big_enough.all():
                idx, Fk, P2, zmax = idx[big_enough], Fk[big_enough], P2[big_enough], zmax[big_enough]
                if len(idx) == 0:
                    continue
            depth = -Z[idx].sum(axis=1) / k
            if light:
                nk = n[idx] / ln[idx, None]
                if not cull:
                    nk = np.where((facing[idx] < 0)[:, None], -nk, nk)   # iluminação dos dois lados
                if self.hq:
                    # ambiente hemisférico: céu (n.y = 1) mais claro, chão (n.y = -1) mais escuro
                    kl = self.ambient * (0.78 + 0.3 * nk[:, 1]) + (1 - self.ambient) * np.clip(nk @ self.light, 0, 1)
                else:
                    kl = self.ambient + (1 - self.ambient) * np.clip(nk @ self.light, 0, 1)
            else:
                kl = None
            fog = (np.clip((depth - self.fog_start) / (self.fog_end - self.fog_start), 0, self.fog_max) * fogk)[:, None]
            # cor final de todas as faces de uma vez: (cor base · Lambert) misturada com a névoa
            base = self._color_array(colors)[fis[idx]] if colors is not None else np.array(color, dtype=np.float32)[None, :]
            lit = base if kl is None else np.minimum(255.0, base * kl[:, None])
            fcol = (lit * (1 - fog) + self.fog_arr * fog).astype(np.int32)
            near_cut = zmax > zc
            ok = ~near_cut
            if ok.any():
                if not ok.all():
                    sel, P2o, fc = idx[ok], P2[ok], fcol[ok]
                else:
                    sel, P2o, fc = idx, P2, fcol
                dep = depth[ok] if not ok.all() else depth
                mn, mx = P2o.min(axis=1), P2o.max(axis=1)
                inside = (mx[:, 0] >= R_.left) & (mn[:, 0] <= R_.right) & (mx[:, 1] >= R_.top) & (mn[:, 1] <= R_.bottom)
                big = (mn[:, 0] < R_.left - 50) | (mx[:, 0] > R_.right + 50) | (mn[:, 1] < R_.top - 50) | (mx[:, 1] > R_.bottom + 50)
                # modo: 2 = recortar na viewport; 1 = suavizar bordas (hq, só faces com mais de ~14 px); 0 = simples
                mode = np.where(big, 2, ((mx - mn).max(axis=1) > 14) if self.hq else 0)
                if not inside.all():
                    P2o, fc, mode, dep = P2o[inside], fc[inside], mode[inside], dep[inside]
                n_ = len(P2o)
                if n_:
                    self.items.extend(zip([layer] * n_, dep.tolist(), ['poly'] * n_, P2o.tolist(), fc.tolist(),
                                          [outline] * n_, mode.tolist()))
            for jj in np.nonzero(near_cut)[0]:                  # faces cortadas pelo plano near
                poly = self._clip_near(list(vc[Fk[jj]]))
                if len(poly) < 3:
                    continue
                pts = self._to_screen(np.array(poly))
                self.items.append((layer, float(depth[jj]), 'poly', pts.tolist(), fcol[jj].tolist(), outline, 2))

    _carr = {}

    def _color_array(self, colors):
        if isinstance(colors, np.ndarray):          # cores que mudam a cada quadro: sem cache
            return colors
        key = id(colors)
        hit = self._carr.get(key)
        if hit is not None and hit[0] is colors:
            return hit[1]
        arr = np.array(colors, dtype=np.float32)
        if len(self._carr) > 3000:
            self._carr.clear()
        self._carr[key] = (colors, arr)
        return arr

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

    def decal(self, origin, u_axis, v_axis, tex, layer=0.5, light=0.95):
        """Imagem 2D 'deitada' num plano horizontal (y constante): mapeamento de
        textura com perspectiva correta.

        origin: canto (u=0, v=0) no mundo; u_axis/v_axis: vetores das bordas;
        tex: array (largura, altura, 4) RGBA (v = 1 é o topo da imagem).
        """
        o = np.asarray(origin, dtype=float)
        U = np.asarray(u_axis, dtype=float)
        Vv = np.asarray(v_axis, dtype=float)
        corners = np.array([o, o + U, o + U + Vv, o + Vv])
        pc = corners @ self.V[:3, :3].T + self.V[:3, 3]
        zc = -self.near
        front = pc[:, 2] <= zc
        if not front.any():
            return
        depth = float(-pc[:, 2].mean())
        if front.all():
            s = self._to_screen(pc)
            x0, y0 = s.min(axis=0)
            x1, y1 = s.max(axis=0)
        else:                                   # cruza o plano near: usa a parte de baixo da tela
            s = self._to_screen(pc[front])
            x0, x1 = self.rect.left, self.rect.right
            y0, y1 = s[:, 1].min(), self.rect.bottom
        x0, y0 = max(self.rect.left, int(x0)), max(self.rect.top, int(y0))
        x1, y1 = min(self.rect.right, int(x1) + 1), min(self.rect.bottom, int(y1) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        self.items.append((layer, depth, 'decal', (x0, y0, x1, y1), o, U, Vv, tex, light))

    def _draw_decal(self, surf, box, o, U, Vv, tex, light):
        x0, y0, x1, y1 = box
        area = (x1 - x0) * (y1 - y0)
        step = 1 if area < 2500 else (2 if area < 30000 else (3 if area < 120000 else 4))
        xs = np.arange(x0, x1, step) + step * 0.5
        ys = np.arange(y0, y1, step) + step * 0.5
        X, Y = np.meshgrid(xs, ys, indexing='ij')
        tf = math.tan(math.radians(self.fov) / 2)
        aspect = self.rect.w / self.rect.h
        nx = ((X - self.rect.x) / self.rect.w * 2 - 1) * tf * aspect
        ny = (1 - (Y - self.rect.y) / self.rect.h * 2) * tf
        R = self.V[:3, :3]
        # direção do raio (espaço da câmera -> mundo): d_mundo = Rᵀ · (nx, ny, -1)
        dx = nx * R[0, 0] + ny * R[1, 0] - R[2, 0]
        dy = nx * R[0, 1] + ny * R[1, 1] - R[2, 1]
        dz = nx * R[0, 2] + ny * R[1, 2] - R[2, 2]
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (o[1] - self.eye[1]) / dy                 # interseção raio x plano y = o.y
        ok = (t > self.near) & np.isfinite(t)
        px = self.eye[0] + t * dx - o[0]
        pz = self.eye[2] + t * dz - o[2]
        uu = (px * U[0] + pz * U[2]) / (U[0] ** 2 + U[2] ** 2)
        vv = (px * Vv[0] + pz * Vv[2]) / (Vv[0] ** 2 + Vv[2] ** 2)
        ok &= (uu >= 0) & (uu < 1) & (vv >= 0) & (vv < 1)
        if not ok.any():
            return
        tw, th = tex.shape[0], tex.shape[1]
        ti = np.clip((uu * tw).astype(np.int32), 0, tw - 1)
        tj = np.clip(((1 - vv) * th).astype(np.int32), 0, th - 1)
        texel = tex[ti, tj]                                    # amostragem (vizinho mais próximo)
        vis = ok & (texel[:, :, 3] > 100)
        if not vis.any():
            return
        f = np.clip((np.where(ok, t, 0) - self.fog_start) / (self.fog_end - self.fog_start), 0, 0.85)[:, :, None]
        col = (texel[:, :, :3].astype(np.float32) * light * (1 - f) + self.fog_arr * f).astype(np.uint8)
        col[~vis] = KEY_COLOR                                  # transparente via colorkey
        # recorta só a região com pixels visíveis (menos área para ampliar e copiar)
        ci = np.nonzero(vis.any(axis=1))[0]
        cj = np.nonzero(vis.any(axis=0))[0]
        i0, i1, j0, j1 = ci[0], ci[-1] + 1, cj[0], cj[-1] + 1
        col, vis = col[i0:i1, j0:j1], vis[i0:i1, j0:j1]
        x0, y0 = x0 + i0 * step, y0 + j0 * step
        # monta a imagem amostrada em baixa resolução e amplia em C (transform.scale)
        small = pygame.Surface(vis.shape, 0, 24)
        pygame.surfarray.blit_array(small, col)
        small.set_colorkey(KEY_COLOR)
        if step > 1:
            small = pygame.transform.scale(small, (vis.shape[0] * step, vis.shape[1] * step))
            small.set_colorkey(KEY_COLOR)
        surf.blit(small, (x0, y0))

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
        self.items.sort(key=lambda it: it[0] * 1e7 - it[1])
        cx0, cy0, cx1, cy1 = self.rect.left, self.rect.top, self.rect.right, self.rect.bottom
        for it in self.items:
            kind = it[2]
            if kind == 'poly':
                pts, col, outline = it[3], it[4], it[5]
                if it[6] == 2:                      # polígono que extrapola a viewport: recorte 2D
                    xs = [q[0] for q in pts]
                    ys = [q[1] for q in pts]
                    if max(xs) < cx0 or min(xs) > cx1 or max(ys) < cy0 or min(ys) > cy1:
                        continue
                    pts = self.clip_rect(pts, cx0 - 1, cy0 - 1, cx1 + 1, cy1 + 1)
                    if len(pts) < 3:
                        continue
                try:
                    pygame.draw.polygon(surf, col, pts)
                    if it[6] == 1:                  # antisserrilhamento das bordas (qualidade alta)
                        pygame.draw.aalines(surf, col, True, pts)
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
            elif kind == 'decal':
                self._draw_decal(surf, *it[3:])
        surf.set_clip(clip)
