import time
import cv2
import numpy as np

from .capture import CameraCapture
from .tracking import TrackingEngine
from .mapping import BlendshapeMapper, BoneMapper
from .smoothing import OneEuroFilter, MultiOneEuroFilter
from .renderer import VRMRenderer
from .gui import VTuberGUI
from .virtual_cam import VirtualCameraOutput

# Landmark indices for drawing
FACE_OVAL  = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
LEFT_EYE   = [33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246]
RIGHT_EYE  = [362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398]
LIPS       = [61,146,91,181,84,17,314,405,321,375,291,308,324,318,402,317,14,87,178,88,95]


def draw_landmarks(frame, face_lms_list, pose_lms_list, h, w):
    if face_lms_list:
        lms = face_lms_list[0]
        for idx in FACE_OVAL:
            x, y = int(lms[idx].x * w), int(lms[idx].y * h)
            cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)
        for idx in LEFT_EYE + RIGHT_EYE:
            x, y = int(lms[idx].x * w), int(lms[idx].y * h)
            cv2.circle(frame, (x, y), 2, (0, 200, 255), -1)
        for idx in LIPS:
            x, y = int(lms[idx].x * w), int(lms[idx].y * h)
            cv2.circle(frame, (x, y), 1, (0, 100, 255), -1)

    if pose_lms_list:
        lms = pose_lms_list[0]
        connections = [(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24)]
        for a, b in connections:
            if a < len(lms) and b < len(lms):
                if lms[a].visibility > 0.5 and lms[b].visibility > 0.5:
                    x1,y1 = int(lms[a].x*w), int(lms[a].y*h)
                    x2,y2 = int(lms[b].x*w), int(lms[b].y*h)
                    cv2.line(frame, (x1,y1), (x2,y2), (255,100,0), 2)
        for i in [11,12,13,14,15,16,23,24]:
            if i < len(lms) and lms[i].visibility > 0.5:
                x, y = int(lms[i].x*w), int(lms[i].y*h)
                cv2.circle(frame, (x,y), 5, (255,50,50), -1)


def draw_hud(frame, blendshapes, fps):
    y = 24
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
    y += 24
    cv2.putText(frame, "Press 'O' to load VRM model", (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
    y += 24
    cv2.putText(frame, "Press 'C' to calibrate neutral pose", (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
    y += 24
    for key, val in blendshapes.items():
        bar_w = int(val * 120)
        cv2.rectangle(frame, (10, y), (10 + bar_w, y+10), (0,200,100), -1)
        cv2.putText(frame, f"{key}: {val:.2f}", (140, y+10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1, cv2.LINE_AA)
        y += 18


class VTuberApp:
    def __init__(self):
        self.capture      = CameraCapture(width=640, height=480)
        self.tracking     = TrackingEngine(self.capture.frame_queue)
        self.blend_mapper = BlendshapeMapper()
        self.bone_mapper  = BoneMapper()
        self.renderer     = VRMRenderer()
        self.v_cam        = VirtualCameraOutput()
        self.gui          = VTuberGUI(
            on_import_vrm=self._load_vrm,
            on_import_fbx=self._load_fbx,
            on_calibrate=self._calibrate,
        )

        self._face_filter_keys = ["eyeBlinkLeft", "eyeBlinkRight", "jawOpen"]
        self.face_filters = {k: OneEuroFilter(min_cutoff=1.0, beta=0.5)
                             for k in self._face_filter_keys}
        self.bone_filters: dict = {}
        self.running = False
        self._latest_result = None
        self._fps_t = time.time()
        self._fps_count = 0
        self._fps = 0.0

    def _load_vrm(self, path):
        print(f"[App] Loading VRM: {path}")
        self.renderer.load_vrm(path)

    def _load_fbx(self, path):
        print(f"[App] FBX import queued: {path}")

    def _calibrate(self):
        if self._latest_result:
            print("[App] Calibrating neutral pose...")
            self.bone_mapper.set_neutral(self._latest_result.pose_landmarks)
        else:
            print("[App] Calibration failed: No tracking result yet")

    def _open_vrm_dialog(self):
        import subprocess
        import platform

        if platform.system() == "Darwin":
            # Native macOS file dialog via osascript to avoid Tkinter/NSApplication conflicts
            # Restrict to vrm and glb/gltf files
            cmd = """
            osascript -e 'POSIX path of (choose file of type {"public.item"} with prompt "Select VRM, GLB or GLTF Model")'
            """
            try:
                path = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
                if path:
                    self._load_vrm(path)
            except subprocess.CalledProcessError:
                pass # User cancelled
        else:
            # Fallback for other OSs
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Select VRM Model",
                filetypes=[("VRM files", "*.vrm"), ("GLB files", "*.glb"), ("All files", "*.*")]
            )
            root.destroy()
            if path:
                self._load_vrm(path)

    def _tick_fps(self):
        self._fps_count += 1
        now = time.time()
        if now - self._fps_t >= 1.0:
            self._fps = self._fps_count / (now - self._fps_t)
            self._fps_count = 0
            self._fps_t = now

    def run(self):
        self.capture.start()
        self.tracking.start()
        self.v_cam.start()
        self.gui.setup()

        print("[App] Running — press Q in the window to quit")
        self.running = True

        smoothed_face = {k: 0.0 for k in self._face_filter_keys}
        smoothed_bones: dict = {}

        try:
            while self.running and self.gui.is_running():
                t_now = time.time()

                # --- tracking result (non-blocking) ---
                result = self.tracking.get_result()
                if result is not None:
                    self._latest_result = result

                    face_weights  = self.blend_mapper.map_face(result.face_landmarks)
                    bone_rotations = self.bone_mapper.map_pose(result.pose_landmarks)

                    for key in self._face_filter_keys:
                        val = face_weights.get(key, 0.0)
                        smoothed_face[key] = self.face_filters[key].update(val, t_now)

                    for key, quat in bone_rotations.items():
                        if key not in self.bone_filters:
                            self.bone_filters[key] = MultiOneEuroFilter(4)
                        smoothed_bones[key] = self.bone_filters[key](quat, t_now)

                    self.renderer.update_blendshapes(smoothed_face)
                    self.renderer.update_pose(smoothed_bones)

                # --- render 3D avatar ---
                self.renderer.render()
                if self.renderer.should_close:
                    self.gui.set_running(False)

                # --- draw preview frame ---
                frame = self.capture.get_frame()
                if frame is not None:
                    h, w = frame.shape[:2]

                    if self._latest_result is not None:
                        draw_landmarks(frame,
                                       self._latest_result.face_landmarks,
                                       self._latest_result.pose_landmarks,
                                       h, w)

                    draw_hud(frame, smoothed_face, self._fps)
                    cv2.imshow("VTuber Studio — Q to quit", frame)
                    self.v_cam.send(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                self._tick_fps()

                # Q or window close → quit
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    self.gui.set_running(False)
                elif key == ord('o'):
                    self._open_vrm_dialog()
                elif key == ord('c'):
                    self._calibrate()

        except KeyboardInterrupt:
            print("[App] Interrupted")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        self.capture.stop()
        self.tracking.stop()
        self.v_cam.stop()
        self.gui.cleanup()
        print("[App] Stopped")


if __name__ == "__main__":
    app = VTuberApp()
    app.run()
