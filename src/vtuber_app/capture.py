import cv2
import threading
import queue
import time

class CameraCapture(threading.Thread):
    def __init__(self, camera_id=0, width=640, height=360, fps=30):
        super().__init__(daemon=True)
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = False
        self.cap = None

    def run(self):
        self.cap = cv2.VideoCapture(self.camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        self.running = True
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            
            # Flip horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Use put_nowait with try-except to avoid blocking if queue is full
            try:
                if self.frame_queue.full():
                    self.frame_queue.get_nowait()
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                pass
            
            time.sleep(1/self.fps)

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def get_frame(self):
        try:
            return self.frame_queue.get(timeout=1.0)
        except queue.Empty:
            return None
