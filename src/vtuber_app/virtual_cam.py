import numpy as np

try:
    import pyvirtualcam
    HAS_VIRTUALCAM = True
except ImportError:
    HAS_VIRTUALCAM = False


class VirtualCameraOutput:
    def __init__(self, width=640, height=480, fps=30):
        self.width  = width
        self.height = height
        self.fps    = fps
        self.cam    = None

    def start(self):
        if not HAS_VIRTUALCAM:
            print("[VirtualCam] pyvirtualcam not installed — skipping virtual camera output")
            return
        try:
            self.cam = pyvirtualcam.Camera(width=self.width, height=self.height, fps=self.fps)
            print(f"[VirtualCam] Started: {self.cam.device}")
        except Exception as e:
            print(f"[VirtualCam] Error starting: {e}")
            self.cam = None

    def send(self, frame: np.ndarray):
        """Send an RGB frame to the virtual camera."""
        if self.cam is None:
            return
        try:
            self.cam.send(frame)
            self.cam.sleep_until_next_frame()
        except Exception as e:
            print(f"[VirtualCam] Send error: {e}")
            self.cam = None

    # keep old name as alias so nothing breaks if called elsewhere
    def send_frame(self, frame: np.ndarray):
        self.send(frame)

    def stop(self):
        if self.cam:
            self.cam.close()
            self.cam = None