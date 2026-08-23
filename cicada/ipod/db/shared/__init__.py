from . import field_base as _fb
from .constants import *
from .extraction import *
from .field_base import *
from .mhbd_defs import *
from .mhbd_defs import MHBD_FIELDS as _mhbd
from .mhia_defs import *
from .mhia_defs import MHIA_FIELDS as _mhia
from .mhii_defs import *
from .mhii_defs import MHII_FIELDS as _mhii
from .mhip_defs import *
from .mhip_defs import MHIP_FIELDS as _mhip
from .mhit_defs import *
from .mhit_defs import MHIT_FIELDS as _mhit
from .mhod_defs import *
from .mhod_defs import MHOD_FIELDS as _mhod
from .mhsd_defs import *
from .mhsd_defs import MHSD_FIELDS as _mhsd
from .mhyp_defs import *
from .mhyp_defs import MHYP_FIELDS as _mhyp

_fb.FIELD_REGISTRY.update({
    "mhbd": _mhbd,
    "mhit": _mhit,
    "mhsd": _mhsd,
    "mhia": _mhia,
    "mhii": _mhii,
    "mhip": _mhip,
    "mhyp": _mhyp,
    "mhod": _mhod,
})
