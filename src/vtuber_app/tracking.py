import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, PoseLandmarker, PoseLandmarkerOptions
import urllib.request
import os
import threading
import queue
import time
from dataclasses import dataclass
from typing import Optional, Any

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
POSE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
FACE_MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")
POSE_MODEL_PATH = os.path.join(MODEL_DIR, "pose_landmarker.task")


def download_model(url, path):
    if not os.path.exists(path):
        print(f"[Tracking] Downloading {os.path.basename(path)}...")
        os.makedirs(MODEL_DIR, exist_ok=True)
        try:
            urllib.request.urlretrieve(url, path)
            print(f"[Tracking] Downloaded {os.path.basename(path)}")
        except Exception as e:
            print(f"[Tracking] Error downloading model: {e}")


@dataclass
class TrackingResult:
    face_landmarks: Any = None
    pose_landmarks: Any = None
    pose_world_landmarks: Any = None
    blendshapes:    Any = None
    timestamp:    float = 0.0


class TrackingEngine(threading.Thread):
    def __init__(self, frame_queue: queue.Queue):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.output_queue = queue.Queue(maxsize=2)
        self.running = False

        download_model(FACE_MODEL_URL, FACE_MODEL_PATH)
        download_model(POSE_MODEL_URL, POSE_MODEL_PATH)

        try:
            face_options = FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=FACE_MODEL_PATH),
                running_mode=mp_vision.RunningMode.VIDEO,
                num_faces=1,
                output_face_blendshapes=True,
            )
            self.face_landmarker = FaceLandmarker.create_from_options(face_options)

            pose_options = PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=POSE_MODEL_PATH),
                running_mode=mp_vision.RunningMode.VIDEO,
            )
            self.pose_landmarker = PoseLandmarker.create_from_options(pose_options)
            print("[Tracking] Models loaded OK")
        except Exception as e:
            print(f"[Tracking] Error initializing MediaPipe: {e}")
            self.face_landmarker = None
            self.pose_landmarker = None

    def run(self):
        self.running = True
        while self.running:
            try:
                item = self.frame_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if item is None:
                continue

            # capture.py sends (frame, ts) tuples — unpack safely
            if isinstance(item, tuple):
                frame, t_ms = item
            else:
                frame = item
                t_ms = int(time.time() * 1000)

            if frame is None or not isinstance(frame, np.ndarray):
                continue

            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                result = TrackingResult(timestamp=time.time())

                if self.face_landmarker:
                    face_res = self.face_landmarker.detect_for_video(mp_image, t_ms)
                    # new API returns lists — store the whole list so mapping.py
                    # can index [0] itself (consistent with how mapping expects it)
                    result.face_landmarks = face_res.face_landmarks  # full list
                    result.blendshapes    = face_res.face_blendshapes

                if self.pose_landmarker:
                    pose_res = self.pose_landmarker.detect_for_video(mp_image, t_ms)
                    result.pose_landmarks = pose_res.pose_landmarks
                    result.pose_world_landmarks = pose_res.pose_world_landmarks

                try:
                    if self.output_queue.full():
                        self.output_queue.get_nowait()
                    self.output_queue.put_nowait(result)
                except queue.Full:
                    pass

            except Exception as e:
                print(f"[Tracking] Frame error: {e}")
                import traceback; traceback.print_exc()

    def stop(self):
        self.running = False
        if self.face_landmarker:
            self.face_landmarker.close()
        if self.pose_landmarker:
            self.pose_landmarker.close()

    def get_result(self) -> Optional[TrackingResult]:
        try:
            return self.output_queue.get(timeout=0.01)
        except queue.Empty:
            return None