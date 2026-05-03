# ============================================================
# SLINGSHOT v10.0 APEX SOVEREIGN — Bridge Loader (Fallback Only)
# ============================================================
# El bridge C fue deprecado en v10.0. Este módulo mantiene
# la interfaz compatible para volume_pattern.py usando
# solo el fallback de Python puro.


class DLLBridge:
    """Stub compatible — siempre usa fallback Python."""
    def __init__(self):
        self.lib = None

    def is_loaded(self):
        return False

bridge = DLLBridge()
