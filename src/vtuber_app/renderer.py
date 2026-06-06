# Stub renderer — draws landmark overlays on the OpenCV frame
# Full OpenGL/VRM renderer will be added in Phase 2
import cv2
import numpy as np
from typing import Dict, Any, List, Optional


class VRMRenderer:
    def __init__(self):
        self.vrm_path = None
        self._blendshapes: Dict[str, float] = {}
        self._bones: Dict[str, Any] = {}
        self._canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        print("[Renderer] OpenCV stub renderer ready (OpenGL in Phase 2)")

    def load_vrm(self, path: str):
        self.vrm_path = path
        print(f"[Renderer] VRM queued for loading: {path}")

    def update_blendshapes(self, weights: Dict[str, float]):
        self._blendshapes = weights

    def update_pose(self, bones: Dict[str, Any]):
        self._bones = bones

    def render(self):
        # No-op — frame is drawn in main loop with overlays
        pass

    def get_canvas(self) -> np.ndarray:
        return self._canvas

    def resize(self, w: int, h: int):
        pass