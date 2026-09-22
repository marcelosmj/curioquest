"""EsObject wire keys under their client-side names (es.EsConstants): K.DALC_ID == "dal0"."""
import json
from pathlib import Path
from types import SimpleNamespace

_CONSTANTS = json.loads(
    (Path(__file__).resolve().parent.parent / "es5" / "es_constants.json").read_text(encoding="utf-8"))

K = SimpleNamespace(**_CONSTANTS)

# wire key -> client name, for readable logs
NAMES = {value: name for name, value in _CONSTANTS.items() if isinstance(value, str)}
