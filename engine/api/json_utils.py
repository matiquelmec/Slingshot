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
        # ── pandas Timestamp ──────────────────────────────────────────────────
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()

        # ── numpy datetime64 ─────────────────────────────────────────────────
        if isinstance(obj, np.datetime64):
            return pd.Timestamp(obj).isoformat()

        # ── Python datetime / date ────────────────────────────────────────────
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()

        # ── numpy integers ────────────────────────────────────────────────────
        if isinstance(obj, (np.integer,)):
            return int(obj)

        # ── numpy floats (incluyendo nan/inf) ─────────────────────────────────
        if isinstance(obj, (np.floating,)):
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                return None  # JSON no soporta NaN/Inf nativamente
            return val

        # ── numpy bool ────────────────────────────────────────────────────────
        if isinstance(obj, np.bool_):
            return bool(obj)

        # ── numpy arrays → list ───────────────────────────────────────────────
        if isinstance(obj, np.ndarray):
            return obj.tolist()

        # ── Decimal ───────────────────────────────────────────────────────────
        if isinstance(obj, Decimal):
            return float(obj)

        # ── Sets → list ───────────────────────────────────────────────────────
        if isinstance(obj, set):
            return list(obj)

        # ── Objetos con .item() (numpy scalars genéricos) ─────────────────────
        if hasattr(obj, "item"):
            return obj.item()

        # ── Fallback: intentar __dict__ ───────────────────────────────────────
        if hasattr(obj, "__dict__"):
            return obj.__dict__

        # Dejar que el padre lance el TypeError informativo
        return super().default(obj)


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

    # dict → recorrer valores
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}

    # list / tuple / set → recorrer elementos
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(item) for item in obj]

    # Objetos con .item() (numpy scalars genéricos)
    if hasattr(obj, "item"):
        return sanitize_for_json(obj.item())

    # Fallback: convertir a string para no perder info
    return str(obj)
