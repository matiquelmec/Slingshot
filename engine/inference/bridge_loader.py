import ctypes
import os
import numpy as np
from engine.core.logger import logger

class GGUFInferenceEngine:
    """
    Motor de Inferencia GGUF Platinum v5.5 (DELTA Optimization).
    Encargado de la comunicación con el Bridge C++ para análisis
    de patrones SMC en microsegundos.
    """

    def __init__(self, lib_path: str, model_path: str, n_ctx: int = 2048):
        self.lib_path = lib_path
        self.model_path = model_path
        self._handle = None
        self._n_embd = 0
        
        # OMEGA Audit: Validación de existencia antes de carga
        if not os.path.exists(lib_path):
            raise FileNotFoundError(f"[OMEGA] Bridge DLL no encontrado en: {lib_path}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"[OMEGA] Modelo GGUF no encontrado en: {model_path}")

        try:
            self.lib = ctypes.CDLL(lib_path)
            self._setup_bindings()
            self._init_engine(n_ctx)
            logger.info(f"🚀 GGUF Engine iniciado: {os.path.basename(model_path)}")
        except Exception as e:
            logger.error(f"❌ Error fatal en Inferencia GGUF: {e}")
            raise

    def _setup_bindings(self):
        """Definición de firmas C para seguridad de tipos (OMEGA Audit)."""
        self.lib.bridge_create.argtypes = [
            ctypes.c_char_p, # model_path
            ctypes.c_int32,  # n_ctx
            ctypes.c_int32,  # n_batch
            ctypes.c_int32,  # n_threads
            ctypes.c_int32,  # n_gpu_layers
            ctypes.c_int32,  # type_k
            ctypes.c_int32,  # type_v
            ctypes.c_int32   # flash_attn
        ]
        self.lib.bridge_create.restype = ctypes.c_void_p

        self.lib.bridge_decode_embd.argtypes = [
            ctypes.c_void_p, # handle
            ctypes.POINTER(ctypes.c_float), # embd
            ctypes.c_int32,  # pos
            ctypes.c_int8    # output
        ]
        self.lib.bridge_decode_embd.restype = ctypes.c_int32

        self.lib.bridge_get_logits.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        self.lib.bridge_get_logits.restype = ctypes.POINTER(ctypes.c_float)

        self.lib.bridge_free.argtypes = [ctypes.c_void_p]
        self.lib.bridge_free.restype = None

    def _init_engine(self, n_ctx: int):
        """Crea el contexto de llama.cpp."""
        self._handle = self.lib.bridge_create(
            self.model_path.encode('utf-8'),
            n_ctx,
            512, # n_batch
            os.cpu_count() or 4, # n_threads
            -1,  # n_gpu_layers (Auto)
            -1,  # type_k (Default)
            -1,  # type_v (Default)
            1    # flash_attn (Enabled)
        )
        if not self._handle:
            raise RuntimeError("[GGUF] Error: No se pudo crear el handle de inferencia")

    def analyze_pattern(self, embedding_vector: np.ndarray, pos: int) -> float:
        """
        Analiza un pool de Market Tokens (SIGMA Volume Pattern).
        Retorna el score de probabilidad de SMC.
        """
        # Convertir a float32 contiguo para C
        embd_data = embedding_vector.astype(np.float32).ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        
        ret = self.lib.bridge_decode_embd(self._handle, embd_data, pos, 1)
        if ret != 0:
            logger.warning(f"[GGUF] Fallo en decode en pos {pos}")
            return 0.0

        # En sistemas de clasificación, tomamos los logits
        logits_ptr = self.lib.bridge_get_logits(self._handle, -1)
        # Asumiendo una salida de 2 clases: [NoSignal, SMCSignal]
        score = logits_ptr[1] 
        return float(score)

    def shutdown(self):
        """Liberación de memoria OMEGA."""
        if self._handle:
            self.lib.bridge_free(self._handle)
            self._handle = None
            logger.info("🗑️ GGUF Inferencia: Memoria liberada correchamente")

    def __del__(self):
        self.shutdown()
