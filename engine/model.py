"""
model.py - Modelos 3D: leitura de OBJ/MTL, simplificação de malha e cache.

O formato Wavefront OBJ é uma REPRESENTAÇÃO POR FACES (B-rep poligonal):
    v  x y z        -> vértices (geometria)
    vt u v          -> coordenadas de textura (UV)
    f  a/ta b/tb .. -> faces (topologia), indexando vértices e UVs
    usemtl nome     -> material da face (cor difusa Kd ou textura map_Kd)

Nosso pipeline desenha cada face com uma cor só (flat shading). Para faces
texturizadas, amostramos a textura no ponto UV médio da face.

Simplificação por AGRUPAMENTO DE VÉRTICES (vertex clustering): o espaço é
dividido numa grade; todos os vértices de uma célula viram um só (a média),
faces que degeneram (vértices repetidos) são descartadas. Reduz milhares de
faces a centenas, mantendo a silhueta - essencial para um renderizador em
Python puro.
"""
import os
import numpy as np
import pygame

from .assets import ASSETS

MODEL_DIR = os.path.join(ASSETS, 'models')


def _srgb(c):
    """Cores Kd do Blender são lineares; corrigimos o gama (≈ 1/2.2) para a tela."""
    return tuple(int(255 * min(1.0, max(0.0, v)) ** (1 / 2.2)) for v in c)


def load_mtl(path, tex_dir=None):
    mats, cur = {}, None
    if not os.path.exists(path):
        return mats
    base = os.path.dirname(path)
    for line in open(path, errors='ignore'):
        p = line.split()
        if not p:
            continue
        if p[0] == 'newmtl':
            cur = ' '.join(p[1:])
            mats[cur] = {'kd': (200, 200, 200), 'tex': None}
        elif p[0] == 'Kd' and cur:
            mats[cur]['kd'] = _srgb([float(x) for x in p[1:4]])
        elif p[0] == 'map_Kd' and cur:
            tp = os.path.join(base, ' '.join(p[1:]))
            try:
                mats[cur]['tex'] = pygame.image.load(tp)
            except Exception:
                pass
    # alguns pacotes nomeiam o material igual à textura (ex.: Wizard_Texture -> Wizard_Texture.png)
    if tex_dir:
        for name, m in mats.items():
            tp = os.path.join(tex_dir, name + '.png')
            if m['tex'] is None and os.path.exists(tp):
                m['tex'] = pygame.image.load(tp)
    return mats


def load_obj(path, texture_override=None, tex_dir=None):
    """Retorna (vértices Nx3, faces [tuplas], cores [rgb por face])."""
    mats = load_mtl(os.path.splitext(path)[0] + '.mtl', tex_dir)
    V, VT, faces, cols = [], [], [], []
    mat = None
    tex_cache = {}
    for line in open(path, errors='ignore'):
        p = line.split()
        if not p:
            continue
        if p[0] == 'v':
            V.append([float(x) for x in p[1:4]])
        elif p[0] == 'vt':
            VT.append([float(x) for x in p[1:3]])
        elif p[0] == 'usemtl':
            mat = mats.get(' '.join(p[1:]), {'kd': (200, 200, 200), 'tex': None})
        elif p[0] == 'f':
            vi, ti = [], []
            for tok in p[1:]:
                parts = tok.split('/')
                vi.append(int(parts[0]) - 1 if int(parts[0]) > 0 else len(V) + int(parts[0]))
                if len(parts) > 1 and parts[1]:
                    ti.append(int(parts[1]) - 1)
            tex = texture_override if texture_override is not None else (mat or {}).get('tex')
            if tex is not None and len(ti) == len(vi) and VT:
                u = sum(VT[t][0] for t in ti) / len(ti)
                v = sum(VT[t][1] for t in ti) / len(ti)
                w, h = tex.get_size()
                x = int((u % 1.0) * (w - 1))
                y = int((1 - (v % 1.0)) * (h - 1))
                c = tex.get_at((x, y))[:3]
            else:
                c = (mat or {}).get('kd', (200, 200, 200))
            # triangula em leque polígonos com mais de 4 lados
            if len(vi) <= 4:
                faces.append(tuple(vi))
                cols.append(tuple(c))
            else:
                for k in range(1, len(vi) - 1):
                    faces.append((vi[0], vi[k], vi[k + 1]))
                    cols.append(tuple(c))
    return np.array(V, dtype=float), faces, cols


def decimate(verts, faces, cols, cells=24):
    """Simplificação por agrupamento de vértices numa grade cells x cells x cells."""
    mn, mx = verts.min(axis=0), verts.max(axis=0)
    size = (mx - mn).max() / cells
    key = np.floor((verts - mn) / size).astype(np.int64)
    ids = key[:, 0] * 1_000_000 + key[:, 1] * 1_000 + key[:, 2]
    uniq, inv = np.unique(ids, return_inverse=True)
    newv = np.zeros((len(uniq), 3))
    np.add.at(newv, inv, verts)
    newv /= np.bincount(inv)[:, None]
    nf, nc, seen = [], [], set()
    for f, c in zip(faces, cols):
        g = []
        for i in f:
            j = int(inv[i])
            if not g or g[-1] != j:
                g.append(j)
        if len(g) > 1 and g[0] == g[-1]:
            g.pop()
        if len(set(g)) < 3:
            continue
        if len(g) > 4:
            g = g[:4]
        k = tuple(sorted(g))
        if k in seen:
            continue
        seen.add(k)
        nf.append(tuple(g))
        nc.append(c)
    return newv, nf, nc


def normalize(verts, height=None, size=None, ground=True):
    """Centraliza no plano XZ, apoia no chão (y = 0) e escala."""
    v = verts.copy()
    mn, mx = v.min(axis=0), v.max(axis=0)
    c = (mn + mx) / 2
    v[:, 0] -= c[0]
    v[:, 2] -= c[2]
    v[:, 1] -= mn[1] if ground else c[1]
    ext = mx - mn
    if height:
        v *= height / ext[1]
    elif size:
        v *= size / ext.max()
    return v


class Model:
    """Malha pronta para o Renderer3D (com níveis de detalhe opcionais)."""

    def __init__(self, verts, faces, cols, lod=None):
        self.verts = np.asarray(verts, dtype=float)
        self.faces = list(faces)
        self.cols = list(cols)
        self.lod = lod          # Model mais simples para longe
        self.radius = float(np.linalg.norm(self.verts, axis=1).max()) if len(self.verts) else 1.0

    def pick(self, dist, far=40.0):
        return self.lod if (self.lod is not None and dist > far) else self


def save_npz(path, verts, faces, cols, verts_lo=None, faces_lo=None, cols_lo=None):
    def pack(fs):
        n = np.array([len(f) for f in fs], dtype=np.int32)
        flat = np.array([i for f in fs for i in f], dtype=np.int32)
        return n, flat
    n, flat = pack(faces)
    d = {'v': verts.astype(np.float32), 'n': n, 'f': flat, 'c': np.array(cols, dtype=np.uint8)}
    if verts_lo is not None:
        n2, flat2 = pack(faces_lo)
        d.update({'v2': verts_lo.astype(np.float32), 'n2': n2, 'f2': flat2, 'c2': np.array(cols_lo, dtype=np.uint8)})
    np.savez_compressed(path, **d)


def _unpack(n, flat):
    out, k = [], 0
    for m in n:
        out.append(tuple(int(x) for x in flat[k:k + m]))
        k += m
    return out


_cache = {}


def load(name):
    """Carrega assets/models/<name>.npz (pré-processado) como Model."""
    if name in _cache:
        return _cache[name]
    d = np.load(os.path.join(MODEL_DIR, name + '.npz'))
    lod = None
    if 'v2' in d:
        lod = Model(d['v2'], _unpack(d['n2'], d['f2']), [tuple(int(x) for x in c) for c in d['c2']])
    m = Model(d['v'], _unpack(d['n'], d['f']), [tuple(int(x) for x in c) for c in d['c']], lod)
    _cache[name] = m
    return m
