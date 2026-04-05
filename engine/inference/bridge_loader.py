import ctypes
import os

class TickNode(ctypes.Structure):
    _fields_ = [
        ("close", ctypes.c_double),
        ("volume", ctypes.c_double),
        ("rvol", ctypes.c_double)
    ]

class DLLBridge:
    def __init__(self):
        self.lib = None
        self._load()

    def _load(self):
        dll_path = os.path.join(os.path.dirname(__file__), "backbone_bridge.dll")
        if os.path.exists(dll_path):
            self.lib = ctypes.CDLL(dll_path)
            self.lib.process_tensor_batch.argtypes = [ctypes.POINTER(TickNode), ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
            self.lib.process_tensor_batch.restype = None

    def is_loaded(self):
        return self.lib is not None

bridge = DLLBridge()
