import time
import cv2
import numpy as np
import threading
import os
from .capture import CameraCapture
from .tracking import TrackingEngine
from .mapping import BlendshapeMapper, BoneMapper
from .smoothing import OneEuroFilter, MultiOneEuroFilter
from .renderer import VRMRenderer
from .gui import VTuberGUI
from .virtual_cam import VirtualCameraOutput

class VTuberApp:
    def __init__(self):
        # Components
        self.capture = CameraCapture()
        self.tracking = TrackingEngine(self.capture.frame_queue)
        self.blend_mapper = BlendshapeMapper()
        self.bone_mapper = BoneMapper()
        self.renderer = VRMRenderer()
        self.v_cam = VirtualCameraOutput()
        
        # GUI
        self.gui = VTuberGUI(
            on_import_vrm=self.load_vrm,
            on_import_fbx=self.load_fbx,
            on_calibrate=self.calibrate
        )
        
        # Smoothing
        self.face_filters = {
            "eyeBlinkLeft": OneEuroFilter(min_cutoff=1.0, beta=0.5),
            "eyeBlinkRight": OneEuroFilter(min_cutoff=1.0, beta=0.5),
            "jawOpen": OneEuroFilter(min_cutoff=1.0, beta=0.5)
        }
        self.bone_filters = {} 

        self.running = False

    def load_vrm(self, path):
        print(f"[App] Loading VRM: {path}")
        self.renderer.load_vrm(path)

    def load_fbx(self, path):
        print(f"[App] Loading FBX: {path}")

    def calibrate(self):
        print("[App] Calibrating...")

    def run(self):
        # macOS OpenCV Authorization Fix: 
        # Must initialize VideoCapture on the main thread to trigger the permission dialog.
        print("[App] Initializing camera...")
        os.environ["OPENCV_AVFOUNDATION_SKIP_AUTH"] = "1"
        temp_cap = cv2.VideoCapture(0)
        if temp_cap.isOpened():
            print("[App] Camera access granted")
            temp_cap.release()
        else:
            print("[App] Warning: Could not open camera on main thread. Permissions might be missing.")

        self.capture.start()
        self.tracking.start()
        self.v_cam.start()
        self.gui.setup()
        
        self.running = True
        try:
            while self.running and self.gui.is_running():
                # 1. Get tracking result
                result = self.tracking.get_result()
                
                if result:
                    # 2. Map landmarks to blendshapes and bones
                    # Use MediaPipe blendshapes if available, else fallback to landmarks
                    if result.blendshapes:
                        # Convert MediaPipe blendshapes to our internal format
                        # MediaPipe blendshape indices: 9: eyeBlinkLeft, 10: eyeBlinkRight, 25: jawOpen
                        face_weights = {
                            "eyeBlinkLeft": result.blendshapes[9].score,
                            "eyeBlinkRight": result.blendshapes[10].score,
                            "jawOpen": result.blendshapes[25].score
                        }
                    else:
                        face_weights = self.blend_mapper.map_face(result.face_landmarks)
                        
                    bone_rotations = self.bone_mapper.map_pose(result.pose_landmarks)
                    
                    # 3. Apply smoothing
                    smoothed_face = {}
                    for key, val in face_weights.items():
                        if key in self.face_filters:
                            smoothed_face[key] = self.face_filters[key].update(val, result.timestamp)
                    
                    smoothed_bones = {}
                    for key, quat in bone_rotations.items():
                        if key not in self.bone_filters:
                            self.bone_filters[key] = MultiOneEuroFilter(4)
                        smoothed_bones[key] = self.bone_filters[key](quat, result.timestamp)
                    
                    # 4. Update renderer
                    self.renderer.update_blendshapes(smoothed_face)
                    self.renderer.update_pose(smoothed_bones)
                
                # 5. Render
                self.renderer.render()
                
                # 6. Update GUI preview
                frame = self.capture.get_frame()
                if frame is not None:
                    # Convert BGR to RGBA for DearPyGui
                    frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA).astype(np.float32) / 255.0
                    self.gui.update_preview(frame_rgba)
                    
                    # 7. Virtual Camera output
                    self.v_cam.send_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                # 8. Render GUI frame
                self.gui.render_frame()
                
        finally:
            self.stop()

    def stop(self):
        self.running = False
        self.capture.stop()
        self.tracking.stop()
        self.v_cam.stop()
        self.gui.cleanup()

if __name__ == "__main__":
    app = VTuberApp()
    app.run()
