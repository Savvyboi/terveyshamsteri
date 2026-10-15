from .cloudnc import CloudNCAdapter
from .dynasty import DynastyAdapter
from .sttinfo import SttInfoAdapter
from .tweb import TwebAdapter

ADAPTERS = {a.platform: a for a in (DynastyAdapter, CloudNCAdapter, TwebAdapter, SttInfoAdapter)}
