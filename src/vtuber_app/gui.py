# Stub GUI — replaced by pure OpenCV window to avoid Metal/DearPyGui segfault
class VTuberGUI:
    def __init__(self, on_import_vrm=None, on_import_fbx=None, on_calibrate=None):
        self.on_import_vrm = on_import_vrm
        self.on_import_fbx = on_import_fbx
        self.on_calibrate  = on_calibrate
        self._running = True
        print("[GUI] OpenCV window mode (DearPyGui in Phase 2)")

    def setup(self):
        pass

    def update_preview(self, frame_rgba):
        pass  # handled in main loop

    def render_frame(self):
        pass

    def is_running(self) -> bool:
        return self._running

    def set_running(self, val: bool):
        self._running = val

    def cleanup(self):
        import cv2
        cv2.destroyAllWindows()