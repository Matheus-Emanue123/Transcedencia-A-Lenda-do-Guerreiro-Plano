"""
bake_gltf.py - Pré-processa um modelo glTF/GLB ANIMADO (com esqueleto) para o jogo.

Uso (a partir da raiz do projeto):
    python tools/bake_gltf.py assets/models/src/dragon.glb assets/models/vorax_anim.npz

O que este script faz, passo a passo:

1. LEITURA DO GLB. Um .glb é um contêiner binário com dois blocos: um JSON que
   descreve a cena (nós, malhas, materiais, esqueleto, animações) e um buffer
   binário com os números (vértices, índices, pesos, quadros-chave). Os
   "accessors" do JSON dizem onde, no buffer, está cada array e qual o seu tipo.

2. HIERARQUIA DE NÓS (grafo de cena). Cada nó tem uma transformação local
   T · R · S (translação, rotação por quatérnio, escala). A matriz global de um
   nó é a do pai vezes a local:  G(nó) = G(pai) · L(nó).
   Os ossos (joints) do esqueleto são nós como outros quaisquer.

3. ANIMAÇÃO POR QUADROS-CHAVE. Cada canal de animação altera a translação, a
   rotação ou a escala de um osso ao longo do tempo. Entre dois quadros-chave
   interpolamos: linear para posição/escala e SLERP (interpolação esférica)
   para os quatérnios de rotação.

4. SKINNING (Linear Blend Skinning). Cada vértice da malha está "preso" a até
   4 ossos, com pesos que somam 1. Na pose atual:

        v' = Σ  wᵢ · G(ossoᵢ) · B⁻¹(ossoᵢ) · v

   B⁻¹ (inverseBindMatrix) leva o vértice do espaço do modelo para o espaço do
   osso na pose de repouso; G leva do osso, já animado, de volta ao mundo.

5. BAKING (pré-cálculo). O skinning é feito AQUI, uma vez só, para vários
   instantes de cada animação. O jogo guarda só as posições dos vértices em
   cada quadro e, durante a execução, interpola linearmente entre dois quadros
   (animação por vértices, ou "morph"):  v(t) = (1 - α)·A + α·B.
   Isso é barato em numpy e mantém o renderizador em Python puro rápido.

6. ANIMAÇÕES SINTÉTICAS. Quando o modelo não traz uma animação de que o jogo
   precisa (ataque, dano, morte), criamos uma em cima de outra: tocamos a base
   (o voo) e somamos rotações extras a alguns ossos (mandíbula, pescoço, asas,
   cauda), moduladas por envelopes no tempo. Rotação extra num osso = multiplicar
   o quatérnio local dele por um quatérnio de eixo-ângulo: q' = q · q(eixo, θ(t)).
   Como os filhos herdam a matriz do pai, girar o pescoço leva junto a cabeça.

7. MODELOS ESTÁTICOS (árvores, arbustos). Mesma leitura, sem animação; a malha é reduzida por
   colapso de arestas com erro quádrico (engine/model.simplify_qem) em dois níveis de detalhe.

8. DOIS NÍVEIS DE QUALIDADE. "hi": a malha original completa (para os gráficos
   bonitos). "lo": a malha simplificada por agrupamento de vértices, calculado
   na pose de repouso e aplicado igualmente a todos os quadros (a média dos
   vértices de cada célula é linear, então a animação continua coerente).
"""
import json
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


# ----------------------------------------------------------------- leitura
class GLB:
    def __init__(self, path):
        b = open(path, 'rb').read()
        magic, _ver, length = struct.unpack('<4sII', b[:12])
        if magic != b'glTF':
            raise ValueError('não é um arquivo .glb')
        off, self.bin = 12, b''
        while off < length:
            clen, ctype = struct.unpack('<II', b[off:off + 8])
            data = b[off + 8:off + 8 + clen]
            if ctype == 0x4E4F534A:          # 'JSON'
                self.json = json.loads(data)
            elif ctype == 0x004E4942:        # 'BIN\0'
                self.bin = data
            off += 8 + clen
        self.nodes = self.json['nodes']

    def accessor(self, i):
        a = self.json['accessors'][i]
        dt, n, cnt = COMP[a['componentType']], NCOMP[a['type']], a['count']
        bv = self.json['bufferViews'][a['bufferView']]
        start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        item = np.dtype(dt).itemsize * n
        stride = bv.get('byteStride', item)
        if stride == item:
            arr = np.frombuffer(self.bin, dt, cnt * n, start).reshape(cnt, n)
        else:                                 # dados intercalados (byteStride)
            raw = np.frombuffer(self.bin, np.uint8, stride * (cnt - 1) + item, start)
            arr = np.lib.stride_tricks.as_strided(raw, (cnt, item), (stride, 1)).copy().view(dt).reshape(cnt, n)
        if a.get('normalized'):
            return arr.astype(float) / np.iinfo(dt).max
        if a['type'] == 'MAT4':               # glTF guarda matrizes por coluna
            return arr.astype(float).reshape(cnt, 4, 4).transpose(0, 2, 1)
        return arr.astype(float) if dt == np.float32 else arr.astype(np.int64)


# ------------------------------------------------------------ matemática
def quat_to_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def quat_axis(axis, deg):
    """Quatérnio (x, y, z, w) de uma rotação de `deg` graus em torno do eixo local 'x', 'y' ou 'z'."""
    h = np.radians(deg) / 2
    v = np.zeros(3)
    v['xyz'.index(axis)] = np.sin(h)
    return np.array([v[0], v[1], v[2], np.cos(h)])


def quat_mul(a, b):
    x1, y1, z1, w1 = a
    x2, y2, z2, w2 = b
    return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])


def bump(a, b):
    """Envelope: 0 fora de [a, b] (fração da duração), sobe e desce suavemente (sen²) dentro."""
    return lambda u: float(np.sin(np.pi * (u - a) / (b - a)) ** 2) if a < u < b else 0.0


def ramp(a, b):
    """Envelope: 0 antes de a, sobe suavemente (smoothstep) até 1 em b e fica em 1."""
    def f(u):
        x = min(1.0, max(0.0, (u - a) / (b - a)))
        return x * x * (3 - 2 * x)
    return f


def slerp(a, b, t):
    d = float(np.dot(a, b))
    if d < 0:                                 # caminho mais curto na esfera
        b, d = -b, -d
    if d > 0.9995:
        q = a + (b - a) * t
    else:
        th = np.arccos(d)
        q = (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)
    return q / np.linalg.norm(q)


def trs(t, r, s):
    M = np.eye(4)
    M[:3, :3] = quat_to_mat(r) * np.asarray(s)[None, :]
    M[:3, 3] = t
    return M


def srgb_mul(texel, factor):
    """Texel (já em sRGB) vezes o baseColorFactor (que vem em sRGB por srgb())."""
    return tuple(int(t * f / 255) for t, f in zip(texel, factor))


def srgb(c):
    """baseColorFactor do glTF é linear; corrigimos o gama para a tela."""
    return tuple(int(255 * min(1.0, max(0.0, v)) ** (1 / 2.2)) for v in c[:3])


# ---------------------------------------------------------- cena e pose
class Scene:
    def __init__(self, g):
        self.g = g
        n = len(g.nodes)
        self.parent = [-1] * n
        for i, nd in enumerate(g.nodes):
            for c in nd.get('children', []):
                self.parent[c] = i
        self.rest = []
        for nd in g.nodes:
            if 'matrix' in nd:
                self.rest.append(('M', np.array(nd['matrix'], float).reshape(4, 4).T))
            else:
                self.rest.append(('T', np.array(nd.get('translation', [0, 0, 0]), float),
                                  np.array(nd.get('rotation', [0, 0, 0, 1]), float),
                                  np.array(nd.get('scale', [1, 1, 1]), float)))
        self.anims = []
        for a in g.json.get('animations', []):
            chans = []
            for ch in a['channels']:
                smp = a['samplers'][ch['sampler']]
                times = g.accessor(smp['input'])[:, 0]
                vals = g.accessor(smp['output'])
                interp = smp.get('interpolation', 'LINEAR')
                if interp == 'CUBICSPLINE':       # (tangente_in, valor, tangente_out): usa só o valor
                    vals = vals[1::3]
                chans.append((ch['target'].get('node'), ch['target']['path'], times, vals, interp))
            dur = max(c[2][-1] for c in chans)
            name = a.get('name', f'anim{len(self.anims)}').split('|')[-1]
            name = name.split('_', 1)[1] if name.startswith('Dragon_') else name
            name = name[:-5] if name.endswith('-loop') else name
            self.anims.append((name, dur, chans))

    def globals_at(self, anim=None, t=0.0, extra=None):
        """Matrizes globais de todos os nós no instante t. extra = {nó: quatérnio} soma rotações locais."""
        local = []
        for r in self.rest:
            local.append(list(r[1:]) if r[0] == 'T' else r[1])
        if anim is not None:
            for node, path, times, vals, interp in anim[2]:
                if node is None or path not in ('translation', 'rotation', 'scale') or self.rest[node][0] != 'T':
                    continue
                k = int(np.searchsorted(times, t, side='right')) - 1
                if k < 0:
                    v = vals[0]
                elif k >= len(times) - 1:
                    v = vals[-1]
                else:
                    a = (t - times[k]) / max(times[k + 1] - times[k], 1e-9)
                    if interp == 'STEP':
                        v = vals[k]
                    elif path == 'rotation':
                        v = slerp(vals[k], vals[k + 1], a)
                    else:
                        v = vals[k] + (vals[k + 1] - vals[k]) * a
                local[node][{'translation': 0, 'rotation': 1, 'scale': 2}[path]] = np.array(v, float)
        for node, q in (extra or {}).items():
            if isinstance(local[node], list):
                local[node][1] = quat_mul(local[node][1], q)
        L = [trs(*l) if isinstance(l, list) else l for l in local]
        G = [None] * len(L)

        def glob(i):
            if G[i] is None:
                p = self.parent[i]
                G[i] = L[i] if p < 0 else glob(p) @ L[i]
            return G[i]
        for i in range(len(L)):
            glob(i)
        return G


def load_texture(g, tex_index):
    """Imagem embutida no .glb (bufferView com um PNG/JPEG) -> array (largura, altura, 3)."""
    import io
    import pygame
    img = g.json['images'][g.json['textures'][tex_index]['source']]
    bv = g.json['bufferViews'][img['bufferView']]
    data = g.bin[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']]
    return pygame.surfarray.array3d(pygame.image.load(io.BytesIO(data)))


def collect_primitives(g):
    """Todas as primitivas de malha: posições, índices, cor por face e dados de skinning.
    Com textura, a cor de cada face é a do texel no ponto UV médio da face (como no model.load_obj)."""
    mats = g.json.get('materials', [])
    prims = []
    for ni, nd in enumerate(g.nodes):
        if 'mesh' not in nd:
            continue
        for p in g.json['meshes'][nd['mesh']]['primitives']:
            if p.get('mode', 4) != 4:            # só triângulos
                continue
            at = p['attributes']
            pos = g.accessor(at['POSITION'])
            idx = g.accessor(p['indices'])[:, 0] if 'indices' in p else np.arange(len(pos))
            m = mats[p['material']] if 'material' in p else {}
            col = srgb(m.get('pbrMetallicRoughness', {}).get('baseColorFactor', [0.8, 0.8, 0.8, 1]))
            tri = idx.reshape(-1, 3)
            fcols = [col] * len(tri)
            tex = m.get('pbrMetallicRoughness', {}).get('baseColorTexture')
            if tex is not None and 'TEXCOORD_0' in at:
                T = load_texture(g, tex['index'])
                uv = g.accessor(at['TEXCOORD_0'])[tri].mean(axis=1)
                tx = ((uv[:, 0] % 1.0) * (T.shape[0] - 1)).astype(int)
                ty = ((uv[:, 1] % 1.0) * (T.shape[1] - 1)).astype(int)     # glTF: v cresce para baixo
                fcols = [srgb_mul(tuple(int(x) for x in c), col) for c in T[tx, ty]]
            pr = {'node': ni, 'pos': pos, 'tri': tri, 'fcols': fcols,
                  'mat': m.get('name', ''), 'skin': nd.get('skin')}
            if pr['skin'] is not None:
                pr['J'] = g.accessor(at['JOINTS_0'])
                pr['W'] = g.accessor(at['WEIGHTS_0'])
            prims.append(pr)
    return prims


def pose_vertices(g, scene, prims, G):
    out = []
    for pr in prims:
        P = np.hstack([pr['pos'], np.ones((len(pr['pos']), 1))])
        if pr['skin'] is not None:
            sk = g.json['skins'][pr['skin']]
            ibm = g.accessor(sk['inverseBindMatrices'])
            JM = np.array([G[j] @ ibm[k] for k, j in enumerate(sk['joints'])])     # (nJ, 4, 4)
            W = pr['W'] / np.maximum(pr['W'].sum(axis=1, keepdims=True), 1e-9)
            M = np.einsum('nk,nkij->nij', W, JM[pr['J']])                          # mistura linear
            v = np.einsum('nij,nj->ni', M, P)[:, :3]
        else:
            v = (P @ G[pr['node']].T)[:, :3]
        out.append(v)
    return np.vstack(out)


# ----------------------------------------------------------------- bake
def bake(src, dst, fps=20, cells=20, length=1.15, recolor=None, keep=None, synth=None):
    from engine.model import cluster
    g = GLB(src)
    scene = Scene(g)
    prims = collect_primitives(g)
    faces, cols, off = [], [], 0
    for pr in prims:
        faces.extend(tuple(int(i) + off for i in t) for t in pr['tri'])
        cols.extend(recolor(pr['mat'], c) if recolor else c for c in pr['fcols'])
        off += len(pr['pos'])

    anims = [a for a in scene.anims if keep is None or a[0] in keep]
    frames = {}
    for a in anims:
        n = max(2, int(round(a[1] * fps)) + 1)
        frames[a[0]] = (a[1], np.array([pose_vertices(g, scene, prims, scene.globals_at(a, t))
                                         for t in np.linspace(0, a[1], n)]))
        print(f'  {a[0]:<16} {a[1]:5.2f}s  {n} quadros')
    byname = {nd.get('name'): i for i, nd in enumerate(g.nodes)}
    for name, sp in (synth or {}).items():
        base = next(a for a in scene.anims if a[0] == sp['base'])
        dur, n = sp['dur'], max(2, int(round(sp['dur'] * fps)) + 1)
        poses = []
        for t in np.linspace(0, dur, n):
            u = t / dur
            tb = sp['base_time'](t, base[1]) if 'base_time' in sp else (t * sp.get('base_speed', 1.0)) % base[1]
            extra = {}
            for bone, axis, deg, env in sp['bones']:
                k = env(u)
                if k:
                    j = byname[bone]
                    extra[j] = quat_mul(extra.get(j, np.array([0, 0, 0, 1.0])), quat_axis(axis, deg * k))
            poses.append(pose_vertices(g, scene, prims, scene.globals_at(base, tb, extra)))
        frames[name] = (dur, np.array(poses))
        print(f'  {name:<16} {dur:5.2f}s  {n} quadros (sintética, sobre {sp["base"]})')

    # solda vértices duplicados (o glTF separa vértices por normal/UV; aqui só a posição importa)
    allf = np.concatenate([f for _, f in frames.values()], axis=0)          # (F, N, 3)
    key = np.round(allf[::max(1, len(allf) // 6)].transpose(1, 0, 2).reshape(len(allf[0]), -1), 4)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    faces = [tuple(int(inv[i]) for i in f) for f in faces]
    keepf = [k for k, f in enumerate(faces) if len(set(f)) == 3]
    faces = [faces[k] for k in keepf]
    cols = [cols[k] for k in keepf]
    for k in frames:
        frames[k] = (frames[k][0], frames[k][1][:, first])

    # normalização: centraliza, apoia no chão (como os outros modelos) e escala pelo comprimento (z)
    ref_name = next((k for k in frames if 'Fly' in k), next(iter(frames)))
    ref = frames[ref_name][1][0]
    mn, mx = ref.min(axis=0), ref.max(axis=0)
    c = (mn + mx) / 2
    s = length / (mx[2] - mn[2])
    shift = np.array([-c[0], -mn[1], -c[2]])
    for k in frames:
        frames[k] = (frames[k][0], (frames[k][1] + shift) * s)
    rest = frames[ref_name][1][0]

    # nível simplificado: agrupamento calculado na pose de repouso, aplicado a todos os quadros
    inv_lo, cnt_lo, faces_lo, cols_lo = cluster(rest, faces, cols, cells)
    d = {'names': np.array(list(frames)), 'fps': np.float32(fps)}
    pack_faces(d, '', faces, cols)
    pack_faces(d, 'lo_', faces_lo, cols_lo)
    for i, (name, (dur, F)) in enumerate(frames.items()):
        d[f'dur{i}'] = np.float32(dur)
        d[f'f{i}'] = F.astype(np.float16)
        lo = np.zeros((len(F), len(cnt_lo), 3))
        for j in range(len(F)):
            np.add.at(lo[j], inv_lo, F[j])
        d[f'lo_f{i}'] = (lo / cnt_lo[None, :, None]).astype(np.float16)
    np.savez_compressed(dst, **d)
    print(f'{dst}: hi {len(rest)} vértices / {len(faces)} faces, lo {len(cnt_lo)} vértices / {len(faces_lo)} faces, '
          f'{os.path.getsize(dst) // 1024} KB')


# ------------------------------------------------------- modelos estáticos
def static_mesh(src, recolor=None):
    """Malha de um .glb na pose de repouso: (vértices, faces, cores, material de cada face)."""
    g = GLB(src)
    scene = Scene(g)
    prims = collect_primitives(g)
    v = pose_vertices(g, scene, prims, scene.globals_at())
    faces, cols, mats, off = [], [], [], 0
    for pr in prims:
        faces.extend(tuple(int(i) + off for i in t) for t in pr['tri'])
        cols.extend(recolor(pr['mat'], c) if recolor else c for c in pr['fcols'])
        mats.extend([pr['mat']] * len(pr['tri']))
        off += len(pr['pos'])
    _, first, inv = np.unique(np.round(v, 4), axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    faces = [tuple(int(inv[i]) for i in f) for f in faces]
    keep = [k for k, f in enumerate(faces) if len(set(f)) == 3]
    return v[first], [faces[k] for k in keep], [cols[k] for k in keep], [mats[k] for k in keep]


def decimate_to(v, faces, cols, target):
    """Agrupamento de vértices com a grade mais fina que ainda respeita o orçamento de faces."""
    from engine.model import decimate
    if len(faces) <= target:
        return v, faces, cols
    best = decimate(v, faces, cols, 3)
    for cells in range(4, 90):
        r = decimate(v, faces, cols, cells)
        if len(r[1]) > target:
            break
        best = r
    return best


def bake_static(src, dst, hi=320, lo=90, recolor=None, height=1.0, two_sided=False, thin=('Wood',)):
    """Modelo parado (árvore, arbusto...) -> .npz com dois níveis de detalhe (faces <= hi e <= lo).
    Faces dos materiais em `thin` (troncos) pesam mais no erro, para não sumirem na simplificação.
    two_sided duplica as faces invertidas (folhagem feita de cartões de um lado só)."""
    from engine import model as MDL
    v, f, c, m = static_mesh(src, recolor)
    v = MDL.normalize(v, height=height)
    w = [30.0 if mat in thin else 1.0 for mat in m]
    vh, fh, ch = MDL.simplify_qem(v, f, c, hi, w)
    vl, fl, cl = MDL.simplify_qem(v, f, c, lo, w)
    if two_sided:
        fh, ch = fh + [t[::-1] for t in fh], ch + ch
        fl, cl = fl + [t[::-1] for t in fl], cl + cl
    MDL.save_npz(dst, vh, fh, ch, vl, fl, cl)
    print(f'{os.path.basename(dst)}: {len(f)} faces -> hi {len(fh)}, lo {len(fl)}')


# ------------------------------------------------------------ manifesto
# Vorax: dragão de MattBas (OpenGameArt, CC-BY-SA 4.0). A textura é uma paleta azul;
# trocamos cada cor pela do Vorax (vermelho-sangue, membranas quase pretas, olhos em brasa).
VORAX_PALETTE = {
    (45, 72, 158): (176, 34, 30),       # escamas do corpo
    (36, 42, 105): (88, 18, 24),        # membrana das asas
    (176, 195, 220): (214, 168, 104),   # ventre
    (200, 93, 116): (120, 14, 22),      # boca e língua
    (230, 230, 230): (240, 232, 214),   # dentes
    (52, 54, 56): (34, 30, 30),         # chifres e garras
    (216, 26, 9): (255, 214, 40),       # olhos
}


def vorax_color(mat, c):
    key = min(VORAX_PALETTE, key=lambda k: sum((x - y) ** 2 for x, y in zip(k, c)))
    return VORAX_PALETTE[key]


def death_time(t, base_dur, dur=1.6):
    """Na morte as asas desaceleram até parar: o tempo da base anda cada vez mais devagar."""
    return (0.8 * (t - t * t / (2 * dur))) % base_dur


VORAX_SYNTH = {
    # ruge para trás com a boca aberta e dá o bote para a frente (quando cospe fogo)
    'Attack': {'base': 'Flying', 'dur': 1.2, 'base_speed': 0.7, 'bones': [
        ('Neck0', 'x', -38, bump(0.0, 0.55)), ('Neck1', 'x', -16, bump(0.0, 0.55)),
        ('Neck0', 'x', 20, bump(0.45, 1.0)), ('Head', 'x', -24, bump(0.45, 1.0)),
        ('Jaw', 'x', 60, bump(0.15, 0.95)), ('Tail1', 'y', 18, bump(0.0, 1.0))]},
    # recua a cabeça com o golpe
    'Hit': {'base': 'Flying', 'dur': 0.7, 'base_speed': 1.3, 'bones': [
        ('Neck0', 'x', -42, bump(0.0, 0.8)), ('Head', 'x', -25, bump(0.0, 0.7)),
        ('Jaw', 'x', 38, bump(0.0, 0.8)), ('Tail1', 'y', -26, bump(0.0, 0.9))]},
    # asas se fecham, pescoço tomba, boca abre
    'Death': {'base': 'Flying', 'dur': 1.6, 'base_time': death_time, 'bones': [
        ('LeftWingTop', 'y', -65, ramp(0.1, 0.9)), ('LeftWingTop', 'x', -25, ramp(0.1, 0.9)),
        ('RightWingTop', 'y', 65, ramp(0.1, 0.9)), ('RightWingTop', 'x', -25, ramp(0.1, 0.9)),
        ('Neck0', 'x', 40, ramp(0.0, 0.7)), ('Neck2', 'x', 20, ramp(0.2, 0.9)),
        ('Jaw', 'x', 45, ramp(0.0, 0.4)), ('Tail0', 'x', 15, ramp(0.2, 1.0))]},
}

# Vegetação (Quaternius, CC0). As cores originais são escuras e apagadas: trocamos por material
# (ou pela cor mais próxima, nos modelos que usam uma textura-paleta).
def by_material(table):
    return lambda mat, c: table.get(mat, c)


def by_nearest(table):
    return lambda mat, c: table[min(table, key=lambda k: sum((x - y) ** 2 for x, y in zip(k, c)))]


WOOD = (112, 78, 60)
STATIC = [   # (origem, destino, faces hi, faces lo, recolor, folhagem de dois lados)
    ('oak', 'oak', 230, 90, by_material({'Green': (82, 150, 66), 'Wood': WOOD}), False),
    ('oak_autumn', 'oak_autumn', 230, 90,
     by_material({'Orange': (216, 118, 48), 'LightOrange': (236, 174, 62), 'Wood': WOOD}), False),
    ('pine', 'pine', 200, 90,
     by_material({'Orange': (40, 104, 72), 'LightOrange': (66, 138, 86), 'Wood': WOOD}), True),
    ('cursed_tree', 'cursed_tree', 200, 80,
     by_nearest({(75, 12, 37): (128, 40, 150), (51, 50, 43): (52, 44, 60)}), True),
    ('dead_tree', 'dead_tree', 140, 60, by_nearest({(127, 80, 46): (120, 104, 92)}), False),
    ('bush', 'bush', 110, 44, by_material({'Green': (70, 136, 60)}), False),
]

# (origem .glb, destino .npz, opções de bake)
MANIFEST = [
    ('assets/models/src/vorax_dragon.glb', 'assets/models/vorax_anim.npz',
     {'recolor': vorax_color, 'keep': ['Flying'], 'synth': VORAX_SYNTH, 'length': 1.5, 'cells': 30}),
]


def pack_faces(d, pre, faces, cols):
    d[pre + 'n'] = np.array([len(f) for f in faces], dtype=np.int32)
    d[pre + 'f'] = np.array([i for f in faces for i in f], dtype=np.int32)
    d[pre + 'c'] = np.array(cols, dtype=np.uint8)


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        bake(sys.argv[1], sys.argv[2])
    else:                                  # sem argumentos: refaz todos os modelos do jogo
        for src, dst, opts in MANIFEST:
            print(src)
            bake(os.path.join(ROOT, src), os.path.join(ROOT, dst), **opts)
        for src, dst, hi, lo, recolor, two in STATIC:
            bake_static(os.path.join(ROOT, 'assets/models/src', src + '.glb'),
                        os.path.join(ROOT, 'assets/models', dst + '.npz'), hi, lo, recolor, two_sided=two)
