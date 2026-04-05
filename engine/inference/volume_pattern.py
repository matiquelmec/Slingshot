import ctypes
import time
from .bridge_loader import bridge, TickNode

# v5.5.2 Vectorizado - Orquestador de Frecuencias (FFT + Tensores)
def analyze_volume_batch(ticks_list):
    """
    Toma una lista de diccionarios de ticks y la procesa en batch 
    usando la infraestructura C compilada para latencia casi-cero.
    """
    if not bridge.is_loaded():
        # Fallback a Python Puro si el DLL falla
        return [min(1.0, (t['volume']*t['rvol'])/max(1, t['close'])) for t in ticks_list]

    num_pairs = len(ticks_list)
    NodeArray = TickNode * num_pairs
    buffer = NodeArray()
    out_scores = (ctypes.c_double * num_pairs)()

    # Traspaso al tensor (marshalling)
    for i, t in enumerate(ticks_list):
        buffer[i].close = t.get('close', 1.0)
        buffer[i].volume = t.get('volume', 0.0)
        buffer[i].rvol = t.get('rvol', 1.0)

    # Inferencia Nativa
    bridge.lib.process_tensor_batch(buffer, num_pairs, out_scores)

    return list(out_scores)
