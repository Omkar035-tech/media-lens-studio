import numpy as np
try:
    import pyvirtualcam
    HAS_VIRTUALCAM = True
except ImportError:
    HAS_VIRTUALCAM = False

class VirtualCameraOutput:
    def __init__(self, width=640, height=360, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.cam = None

    def start(self):
        if not HAS_VIRTUALCAM:
            print("[VirtualCam] pyvirtualcam not installed — skipping virtual camera output")
            return

        try:
            self.cam = pyvirtualcam.Camera(width=self.width, height=self.height, fps=self.fps)
            print(f"[VirtualCam] Started: {self.cam.device}")
        except Exception as e:
            print(f"[VirtualCam] Error starting virtual camera: {e}")
            self.cam = None

    def send_frame(self, frame):
        if self.cam:
            try:
                # frame should be RGB
                self.cam.send(frame)
                self.cam.sleep_until_next_frame()
            except Exception as e:
                print(f"[VirtualCam] Error sending frame: {e}")
                self.cam = None

    def stop(self):
        if self.cam:
            self.cam.close()
            self.cam = None
