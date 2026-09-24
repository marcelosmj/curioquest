"""EsObject wire keys under their client-side names (es.EsConstants): K.DALC_ID == "dal0"."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

# No Android o pacote e servido de dentro de um zip pelo Chaquopy, entao o vizinho
# es5/es_constants.json nao existe como arquivo.  CURIOQUEST_ES5_DIR aponta para onde
# o app extraiu os dados; sem a variavel, o caminho normal ao lado do codigo vale.
_ES5_DIR = Path(os.environ.get("CURIOQUEST_ES5_DIR")
                or Path(__file__).resolve().parent.parent / "es5")
_CONSTANTS = json.loads((_ES5_DIR / "es_constants.json").read_text(encoding="utf-8"))

K = SimpleNamespace(**_CONSTANTS)

# wire key -> client name, for readable logs
NAMES = {value: name for name, value in _CONSTANTS.items() if isinstance(value, str)}
