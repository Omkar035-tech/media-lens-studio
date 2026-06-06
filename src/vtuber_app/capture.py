import cv2
import threading
import queue
import time

class CameraCapture:
    def __init__(self, camera_id=0, width=640, height=480, fps=30):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_queue = queue.Queue(maxsize=2)
        self._running = False
        self._thread = None
        self._latest_frame = None
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        cap = cv2.VideoCapture(self.camera_id)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        if not cap.isOpened():
            print("[Capture] ERROR: Could not open camera")
            return

        print(f"[Capture] Camera opened: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            frame = cv2.flip(frame, 1)
            with self._lock:
                self._latest_frame = frame
            try:
                if self.frame_queue.full():
                    self.frame_queue.get_nowait()
                ts = int(time.time() * 1000)
                self.frame_queue.put_nowait((frame, ts))
            except queue.Full:
                pass

        cap.release()
        print("[Capture] Camera released")

    def get_frame(self):
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)