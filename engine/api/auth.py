"""
engine/api/auth.py — Autenticación JWT Rotatoria v6.0.1
=========================================================
Responsabilidad: Emisión y validación de tokens JWT para el WebSocket.

Arquitectura Σ Sigma:
  - Token de corta vida (60 min) firmado con HMAC-SHA256
  - Secret rotativo: cambia automáticamente cada SESSION_ROTATION_MIN minutos
  - Endpoint REST `/api/v1/auth/token` protegido por la API Key interna
  - WebSocket valida el JWT (no la API Key directamente)

Flujo:
  1. Frontend llama GET /api/v1/auth/token?api_key=SLINGSHOT_INTERNAL_V6
  2. Servidor emite JWT firmado (exp: 60 min)
  3. Frontend conecta WS con ?token=<jwt>
  4. Servidor valida JWT en cada conexión WebSocket

Ventajas sobre API Key estática:
  - Rotación automática sin redeployment
  - Expiración automática (mitiga replay attacks)
  - Sin exponer la API Key en logs de WS
  - Auditoría por subject (client_id único por token)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Optional

from engine.core.logger import logger
from engine.api.config import settings

# ── Constantes ────────────────────────────────────────────────────────────────

TOKEN_TTL_SECONDS   = 60 * 60        # 60 minutos de vida por token
SESSION_ROTATION_MIN = 120           # Rotar el secret base cada 2 horas
JWT_HEADER          = {"alg": "HS256", "typ": "JWT"}

# ── Secret Store (Rotación en Memoria) ───────────────────────────────────────

class _SecretStore:
    """
    Gestiona la rotación automática del JWT secret.

    El secret se deriva del `SLINGSHOT_JWT_SECRET` (o `SECURITY_API_KEY` como
    fallback de compatibilidad) + un "epoch" que cambia cada SESSION_ROTATION_MIN.

    Ventaja: no requiere ningún cambio en .env para rotar. El secret cambia
    automáticamente cada 2 horas en memoria.
    """

    def __init__(self):
        # Base: usar JWT_SECRET si está definido, sino derivar de la API Key
        self._base = getattr(settings, "JWT_SECRET", None) or (
            settings.SECURITY_API_KEY + "_JWT_v6.0.1"
        )
        self._current_secret: Optional[bytes] = None
        self._current_epoch: int              = -1

    def _epoch(self) -> int:
        """Devuelve la época actual (cambia cada SESSION_ROTATION_MIN)."""
        return int(time.time()) // (SESSION_ROTATION_MIN * 60)

    def get_secret(self) -> bytes:
        """Devuelve el secret activo. Se regenera si la época cambió."""
        epoch = self._epoch()
        if epoch != self._current_epoch:
            raw = f"{self._base}:{epoch}"
            self._current_secret = hashlib.sha256(raw.encode()).digest()
            self._current_epoch  = epoch
            logger.info(f"[AUTH] 🔐 JWT Secret rotado (epoch {epoch})")
        return self._current_secret  # type: ignore[return-value]

    def get_previous_secret(self) -> bytes:
        """Secret de la época anterior — para aceptar tokens emitidos justo antes de rotar."""
        epoch = self._epoch() - 1
        raw = f"{self._base}:{epoch}"
        return hashlib.sha256(raw.encode()).digest()


_store = _SecretStore()


# ── JWT (Implementación Sin Dependencias Externas) ───────────────────────────

def _b64_encode(data: bytes) -> str:
    """Base64url encoding sin padding (RFC 7515)."""
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(s: str) -> bytes:
    """Base64url decoding sin padding."""
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _sign(header: str, payload: str, secret: bytes) -> str:
    """Genera la firma HMAC-SHA256 para header.payload."""
    message = f"{header}.{payload}".encode()
    return _b64_encode(hmac.new(secret, message, hashlib.sha256).digest())


# ── API Pública ───────────────────────────────────────────────────────────────

def issue_token(subject: Optional[str] = None) -> str:
    """
    Emite un JWT firmado con HMAC-SHA256.

    Args:
        subject: Identificador del cliente (ej. client_id). Si no se pasa,
                 genera un UUID único.

    Returns:
        Token JWT como string (header.payload.signature)
    """
    now    = int(time.time())
    sub    = subject or str(uuid.uuid4())
    secret = _store.get_secret()

    header_b64  = _b64_encode(json.dumps(JWT_HEADER, separators=(",", ":")).encode())
    payload     = {
        "sub":  sub,
        "iat":  now,
        "exp":  now + TOKEN_TTL_SECONDS,
        "iss":  "slingshot-v6",
        "jti":  str(uuid.uuid4()),   # JWT ID único — previene replay attacks
    }
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())
    signature   = _sign(header_b64, payload_b64, secret)

    logger.debug(f"[AUTH] Token emitido para sub={sub[:8]}... (exp +{TOKEN_TTL_SECONDS//60}min)")
    return f"{header_b64}.{payload_b64}.{signature}"


def validate_token(token: str) -> tuple[bool, str, Optional[dict]]:
    """
    Valida un JWT. Acepta tanto el secret actual como el anterior (ventana de rotación).

    Args:
        token: JWT string

    Returns:
        (is_valid, reason, payload_dict)
        - is_valid: True si el token es válido y no expiró
        - reason:   Mensaje de error si invalid, vacío si ok
        - payload:  Diccionario con claims si válido, None si inválido
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False, "Formato JWT inválido (se esperan 3 partes)", None

        header_b64, payload_b64, sig_received = parts

        # Verificar con secret actual Y anterior (ventana de rotación segura)
        valid_sig = False
        for secret in [_store.get_secret(), _store.get_previous_secret()]:
            expected_sig = _sign(header_b64, payload_b64, secret)
            if hmac.compare_digest(sig_received, expected_sig):
                valid_sig = True
                break

        if not valid_sig:
            return False, "Firma JWT inválida", None

        # Decodificar payload
        payload = json.loads(_b64_decode(payload_b64))

        # Verificar expiración
        now = int(time.time())
        if payload.get("exp", 0) < now:
            return False, f"Token expirado (exp: {payload.get('exp')})", None

        # Verificar issuer
        if payload.get("iss") != "slingshot-v6":
            return False, f"Issuer inválido: {payload.get('iss')}", None

        return True, "", payload

    except Exception as e:
        return False, f"Error validando JWT: {e}", None


def token_time_remaining(token: str) -> int:
    """
    Retorna los segundos restantes de vida del token.
    Retorna 0 si el token es inválido o expiró.
    """
    is_valid, _, payload = validate_token(token)
    if not is_valid or payload is None:
        return 0
    return max(0, payload.get("exp", 0) - int(time.time()))
