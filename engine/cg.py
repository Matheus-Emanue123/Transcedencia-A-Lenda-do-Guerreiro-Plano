"""
cg.py - Algoritmos de Computação Gráfica implementados "na mão".

Tudo o que o jogo exige do jogador é calculado aqui, seguindo os slides da
disciplina (Prof. Raulivan Rodrigo - CEFET-MG):

  * Rasterização: Bresenham (retas) e Ponto-Médio (circunferências)
  * Cores: RGB <-> CMYK, composição alpha, chroma key
  * Transformações 2D em coordenadas homogêneas (matrizes 3x3)
  * Sistemas de coordenadas: SRU -> SRN -> SRD (window/viewport)
  * Curvas de Bézier (algoritmo de De Casteljau)
  * Transformações 3D (matrizes 4x4), projeções ortográfica e perspectiva,
    câmera virtual (lookAt)
  * Superfícies de revolução e malhas poligonais
"""
import math
import numpy as np


# =============================================================================
# 1. RASTERIZAÇÃO
# =============================================================================
def bresenham(x0, y0, x1, y1):
    """Algoritmo de Bresenham (1962) - apenas soma/subtração de inteiros.

    Retorna a lista de passos: (x, y, erro) - o erro acumulado ANTES do passo,
    para que o jogo possa mostrar o estado interno do algoritmo.
    Segue exatamente o pseudocódigo da aula "Desenhar primitivas".
    """
    passos = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    erro = dx - dy
    x, y = x0, y0
    while True:
        passos.append((x, y, erro))
        if x == x1 and y == y1:
            break
        e2 = 2 * erro
        if e2 > -dy:
            erro -= dy
            x += sx
        if e2 < dx:
            erro += dx
            y += sy
    return passos


def midpoint_circle(cx, cy, r):
    """Algoritmo do Ponto Médio para circunferências.

    Calcula apenas 1/8 da circunferência (2º octante) e espelha os outros 7
    por simetria. Retorna uma lista de passos: (d, [8 pontos]).
    """
    passos = []
    x, y = 0, r
    d = 1 - r
    while x <= y:
        pts = [(cx + x, cy + y), (cx + y, cy + x), (cx + y, cy - x), (cx + x, cy - y),
               (cx - x, cy - y), (cx - y, cy - x), (cx - y, cy + x), (cx - x, cy + y)]
        passos.append((d, pts))
        if d < 0:
            d += 2 * x + 3
        else:
            d += 2 * (x - y) + 5
            y -= 1
        x += 1
    return passos


# =============================================================================
# 2. CORES
# =============================================================================
def cmyk_to_rgb(c, m, y, k):
    """c, m, y, k em [0,1]  ->  (R,G,B) em [0,255]."""
    r = 255 * (1 - c) * (1 - k)
    g = 255 * (1 - m) * (1 - k)
    b = 255 * (1 - y) * (1 - k)
    return (round(r), round(g), round(b))


def rgb_to_cmyk(r, g, b):
    """(R,G,B) em [0,255]  ->  (c,m,y,k) em [0,1]."""
    rp, gp, bp = r / 255, g / 255, b / 255
    k = 1 - max(rp, gp, bp)
    if k >= 1:
        return (0.0, 0.0, 0.0, 1.0)
    c = (1 - rp - k) / (1 - k)
    m = (1 - gp - k) / (1 - k)
    y = (1 - bp - k) / (1 - k)
    return (c, m, y, k)


def alpha_blend(fg, bg, a):
    """Composição alpha:  C = a*F + (1-a)*B."""
    return tuple(a * f + (1 - a) * b for f, b in zip(fg, bg))


def color_dist(c1, c2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def chroma_key(fg_arr, bg_arr, key, tol):
    """Chroma key vetorizado (numpy).

    fg_arr / bg_arr: arrays (W,H,3). Pixels de fg cuja distância euclidiana
    no espaço RGB até a cor-chave seja < tol são substituídos por bg.
    Retorna (imagem_resultante, mascara_removida).
    """
    diff = fg_arr.astype(np.int32) - np.array(key, dtype=np.int32)
    dist = np.sqrt((diff * diff).sum(axis=2))
    mask = dist < tol
    out = np.where(mask[..., None], bg_arr, fg_arr)
    return out.astype(np.uint8), mask


# =============================================================================
# 3. TRANSFORMAÇÕES 2D - COORDENADAS HOMOGÊNEAS (3x3)
# =============================================================================
def T2(tx, ty):
    return np.array([[1, 0, tx], [0, 1, ty], [0, 0, 1]], dtype=float)


def S2(sx, sy):
    return np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1]], dtype=float)


def R2(graus):
    a = math.radians(graus)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def Ref2(eixo):
    """Reflexão: eixo='x' espelha em torno do eixo X (y -> -y);
    eixo='y' espelha em torno do eixo Y (x -> -x)."""
    if eixo == 'x':
        return np.array([[1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=float)
    return np.array([[-1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)


def Sh2(shx, shy):
    """Cisalhamento: x' = x + shx*y ; y' = y + shy*x."""
    return np.array([[1, shx, 0], [shy, 1, 0], [0, 0, 1]], dtype=float)


def apply2(M, pts):
    """Aplica uma matriz homogênea 3x3 a uma lista de pontos (x,y)."""
    P = np.array([[x, y, 1.0] for x, y in pts]).T      # 3 x N
    R = M @ P
    return [(R[0, i] / R[2, i], R[1, i] / R[2, i]) for i in range(R.shape[1])]


# =============================================================================
# 4. SISTEMAS DE COORDENADAS  (SRU -> SRN -> SRD)
# =============================================================================
def sru_to_srn(xw, yw, win):
    """win = (xmin, xmax, ymin, ymax) no SRU (universo). Retorna SRN em [0,1]."""
    xmin, xmax, ymin, ymax = win
    return ((xw - xmin) / (xmax - xmin), (yw - ymin) / (ymax - ymin))


def srn_to_srd(xn, yn, vp):
    """vp = (x, y, largura, altura) em pixels. O eixo Y do dispositivo
    cresce para BAIXO, por isso usamos (1 - yn)."""
    vx, vy, vw, vh = vp
    return (vx + xn * vw, vy + (1 - yn) * vh)


def sru_to_srd(xw, yw, win, vp):
    xn, yn = sru_to_srn(xw, yw, win)
    return srn_to_srd(xn, yn, vp)


def srd_to_sru(xd, yd, win, vp):
    vx, vy, vw, vh = vp
    xn = (xd - vx) / vw
    yn = 1 - (yd - vy) / vh
    xmin, xmax, ymin, ymax = win
    return (xmin + xn * (xmax - xmin), ymin + yn * (ymax - ymin))


# =============================================================================
# 5. CURVAS DE BÉZIER
# =============================================================================
def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def de_casteljau(pts, t):
    """Retorna todos os níveis da construção de De Casteljau.
    O último nível contém um único ponto: B(t)."""
    niveis = [list(pts)]
    atual = list(pts)
    while len(atual) > 1:
        atual = [lerp(atual[i], atual[i + 1], t) for i in range(len(atual) - 1)]
        niveis.append(atual)
    return niveis


def bezier(pts, t):
    return de_casteljau(pts, t)[-1][0]


def bezier_curve(pts, n=60, t0=0.0, t1=1.0):
    return [bezier(pts, t0 + (t1 - t0) * i / n) for i in range(n + 1)]


def bernstein_cubic(pts, t):
    """Forma polinomial (base de Bernstein) - equivalente a De Casteljau."""
    p0, p1, p2, p3 = pts
    u = 1 - t
    b0, b1, b2, b3 = u ** 3, 3 * u * u * t, 3 * u * t * t, t ** 3
    return (b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0],
            b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1])


# =============================================================================
# 6. TRANSFORMAÇÕES 3D (4x4), PROJEÇÕES E CÂMERA
# =============================================================================
def T3(tx, ty, tz):
    M = np.eye(4)
    M[:3, 3] = (tx, ty, tz)
    return M


def S3(sx, sy, sz):
    return np.diag([sx, sy, sz, 1.0])


def Rx(graus):
    a = math.radians(graus)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], dtype=float)


def Ry(graus):
    a = math.radians(graus)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], dtype=float)


def Rz(graus):
    a = math.radians(graus)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)


def normalize(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def look_at(eye, center, up):
    """Matriz de visualização (câmera virtual) - equivalente ao gluLookAt.

    f = direção de projeção (eye -> center), s = f x up, u = s x f.
    """
    eye = np.asarray(eye, dtype=float)
    f = normalize(np.asarray(center, dtype=float) - eye)
    s = normalize(np.cross(f, up))
    u = np.cross(s, f)
    M = np.eye(4)
    M[0, :3] = s
    M[1, :3] = u
    M[2, :3] = -f
    M[:3, 3] = (-s @ eye, -u @ eye, f @ eye)
    return M


def perspective(fovy_graus, aspect, near, far):
    """Matriz de projeção perspectiva (equivalente ao gluPerspective)."""
    f = 1.0 / math.tan(math.radians(fovy_graus) / 2)
    M = np.zeros((4, 4))
    M[0, 0] = f / aspect
    M[1, 1] = f
    M[2, 2] = (far + near) / (near - far)
    M[2, 3] = (2 * far * near) / (near - far)
    M[3, 2] = -1
    return M


def ortho(left, right, bottom, top, near, far):
    """Matriz de projeção ortográfica (equivalente ao glOrtho)."""
    M = np.eye(4)
    M[0, 0] = 2 / (right - left)
    M[1, 1] = 2 / (top - bottom)
    M[2, 2] = -2 / (far - near)
    M[0, 3] = -(right + left) / (right - left)
    M[1, 3] = -(top + bottom) / (top - bottom)
    M[2, 3] = -(far + near) / (far - near)
    return M


def apply4(M, verts):
    """verts: array (N,3) -> array (N,3) transformado (com divisão por w)."""
    V = np.hstack([verts, np.ones((len(verts), 1))])
    R = V @ M.T
    w = R[:, 3:4]
    w[np.abs(w) < 1e-9] = 1e-9
    return R[:, :3] / w


def proj_ortografica(pts3):
    """Projeção paralela ortográfica no plano z=0: (x,y,z) -> (x,y)."""
    return [(p[0], p[1]) for p in pts3]


def proj_perspectiva(pts3, d):
    """Projeção perspectiva com centro de projeção na origem e plano de
    projeção em z = d:   x' = d*x/z ,  y' = d*y/z."""
    out = []
    for x, y, z in pts3:
        z = max(z, 1e-3)
        out.append((d * x / z, d * y / z))
    return out


# =============================================================================
# 7. MALHAS / SUPERFÍCIES
# =============================================================================
def revolution(profile, segmentos, fechar_topo=True):
    """Superfície de revolução: gira um perfil 2D (r, y) em torno do eixo Y.

    S(u, v) = ( r(u) cos v ,  y(u) ,  r(u) sin v )
    Retorna (vertices Nx3, faces [quads/tris como tuplas de índices]).
    """
    verts = []
    n = len(profile)
    for j in range(segmentos):
        v = 2 * math.pi * j / segmentos
        cv, sv = math.cos(v), math.sin(v)
        for (r, y) in profile:
            verts.append((r * cv, y, r * sv))
    faces = []
    for j in range(segmentos):
        j2 = (j + 1) % segmentos
        for i in range(n - 1):
            a = j * n + i
            b = j * n + i + 1
            c = j2 * n + i + 1
            d = j2 * n + i
            faces.append((a, b, c, d))
    return np.array(verts, dtype=float), faces


def box(sx=1, sy=1, sz=1):
    x, y, z = sx / 2, sy / 2, sz / 2
    v = np.array([(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                  (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)], dtype=float)
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]
    return v, f


def cube_edges():
    v, _ = box(2, 2, 2)
    e = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
         (0, 4), (1, 5), (2, 6), (3, 7)]
    return v, e


def pyramid_edges():
    v = np.array([(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1), (0, 1.2, 0)], dtype=float)
    e = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4)]
    return v, e


def prism_edges():
    """Prisma triangular."""
    h = 1.3
    tri = [(0, 1.0), (-0.866, -0.5), (0.866, -0.5)]
    v = [(x, y, -h) for x, y in tri] + [(x, y, h) for x, y in tri]
    e = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3), (1, 4), (2, 5)]
    return np.array(v, dtype=float), e


def cylinder(r=1, h=2, seg=12, tampa=True):
    prof = [(0, 0), (r, 0), (r, h), (0, h)] if tampa else [(r, 0), (r, h)]
    return revolution(prof, seg)


def cone(r=1, h=2, seg=12):
    return revolution([(0, 0), (r, 0), (0, h)], seg)


def octahedron(s=1.0):
    v = np.array([(s, 0, 0), (-s, 0, 0), (0, s * 1.4, 0), (0, -s * 1.4, 0), (0, 0, s), (0, 0, -s)], dtype=float)
    f = [(2, 4, 0), (2, 0, 5), (2, 5, 1), (2, 1, 4), (3, 0, 4), (3, 5, 0), (3, 1, 5), (3, 4, 1)]
    return v, f


def hausdorff(A, B):
    """Distância de Hausdorff entre dois conjuntos de pontos 2D."""
    if not A or not B:
        return 1e9
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    D = np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(axis=2))
    return max(D.min(axis=1).max(), D.min(axis=0).max())
