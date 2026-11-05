from .fase1_raster import Fase1
from .fase2_cores import Fase2
from .fase3_chroma import Fase3
from .fase4_transf import Fase4
from .fase5_coords import Fase5
from .fase6_bezier import Fase6
from .fase7_proj import Fase7
from .fase8_revol import Fase8
from .fase9_camera import Fase9
from . import ending, menu, intro  # noqa: F401

PHASES = [Fase1, Fase2, Fase3, Fase4, Fase5, Fase6, Fase7, Fase8, Fase9]
