"""
json_utils.py — Serializer JSON robusto y centralizado para Slingshot Gen 1.

Resuelve el problema raíz de 'Object of type Timestamp is not JSON serializable'
de forma global, sin parchear cada punto de emisión individualmente.

Tipos soportados:
  - pandas.Timestamp / numpy.datetime64
  - numpy int/float (int32, int64, float32, float64, etc.)
  - Python datetime / date
  - decimal.Decimal
  - Cualquier objeto con .item() (numpy scalars)
  - Sets → lists
  - Objetos con __dict__ → dict
"""

import json
import math
from datetime import datetime, date
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


class SlingshotJSONEncoder(json.JSONEncoder):
    """
    Encoder JSON personalizado que convierte tipos no nativos de Python
    a representaciones serializables de forma segura y predecible.
    """

    def default(self, obj: Any) -> Any:  # noqa: ANN401
        try:
            return sanitize_for_json(obj)
        except Exception:
            # Si sanitize_for_json falla por algo extremo, dejar que el padre intente lo último
            try:
                return super().default(obj)
            except TypeError:
                return str(obj) # Fallback final absoluto: stringizar para no tirar el pipeline


def safe_dumps(obj: Any, **kwargs) -> str:
    """Serializa a JSON usando SlingshotJSONEncoder. Nunca lanza TypeError."""
    return json.dumps(obj, cls=SlingshotJSONEncoder, **kwargs)


def safe_loads(s: str) -> Any:
    """Deserializa JSON estándar."""
    return json.loads(s)


def sanitize_for_json(obj: Any) -> Any:
    """
    Convierte recursivamente un objeto complejo a tipos nativos de Python
    puros (dict, list, str, int, float, bool, None).

    Útil para limpiar resultados del engine antes de send_json().
    """
    if obj is None:
        return None

    # Tipos nativos ya serializables — devolver directamente
    if isinstance(obj, (bool, int, str)):
        return obj

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # pandas Timestamp
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    # numpy datetime64
    if isinstance(obj, np.datetime64):
        return pd.Timestamp(obj).isoformat()

    # Python datetime / date
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()

    # numpy integers → int
    if isinstance(obj, np.integer):
        return int(obj)

    # numpy floats → float | None
    if isinstance(obj, np.floating):
        val = float(obj)
        return None if (math.isnan(val) or math.isinf(val)) else val

    # numpy bool → bool
    if isinstance(obj, np.bool_):
        return bool(obj)

    # numpy array → list recursivo
    if isinstance(obj, np.ndarray):
        return [sanitize_for_json(item) for item in obj.tolist()]

    # Decimal → float
    if isinstance(obj, Decimal):
        return float(obj)

    # Fallback paranoico por nombre de tipo (Robusto contra recargas de módulos o mismatches)
    type_name = type(obj).__name__
    if type_name in ['Timestamp', 'datetime64', 'datetime', 'date']:
        try:
            return obj.isoformat()
        except AttributeError:
            return str(obj)

    if type_name in ['int32', 'int64', 'long']:
        return int(obj)
    
    if type_name in ['float32', 'float64', 'decimal']:
        return float(obj)

    # dict → recorrer valores
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}

    # list / tuple / set → recorrer elementos
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(item) for item in obj]

    # Fallback final absoluto para evitar tirar el pipeline: stringizar
    try:
        return str(obj)
    except:
        return "[NON-SERIALIZABLE]"
