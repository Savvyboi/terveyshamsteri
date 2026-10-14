from .cloudnc import CloudNCAdapter
from .dynasty import DynastyAdapter
from .tweb import TwebAdapter

ADAPTERS = {a.platform: a for a in (DynastyAdapter, CloudNCAdapter, TwebAdapter)}
