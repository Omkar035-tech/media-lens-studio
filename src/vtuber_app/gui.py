import cv2
import numpy as np
from typing import Dict, List, Optional, Callable, Tuple

class BoneMappingUI:
    """
    Standalone OpenCV window: left = camera bones, right = model bones.
    User clicks a camera bone, clicks a model bone → creates mapping.
    Slider area at bottom for gain/smoothing per bone pair.
    """

    PANEL_W = 420
    PANEL_H = 600
    COL_W   = 180
    ROW_H   = 34
    PAD_X   = 20
    PAD_Y   = 60

    def __init__(self):
        self.camera_bones: List[str] = []
        self.model_bones:  List[str] = []
        self.mapping: Dict[str, str] = {}        # cam_bone → model_bone
        self.gains:   Dict[str, float] = {}      # cam_bone → gain [0.1–3.0]
        self._selected_cam: Optional[str] = None
        self._panel = np.zeros((self.PANEL_H, self.PANEL_W, 3), dtype=np.uint8)
        self._drag_slider: Optional[str] = None  # bone name being dragged
        self._window = "Bone Mapper"
        self._open = False

    def set_camera_bones(self, names: List[str]):
        self.camera_bones = names
        for n in names:
            if n not in self.gains:
                self.gains[n] = 1.0

    def set_model_bones(self, names: List[str]):
        self.model_bones = names

    def open(self):
        cv2.namedWindow(self._window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self._window, self.PANEL_W, self.PANEL_H)
        cv2.setMouseCallback(self._window, self._on_mouse)
        self._open = True

    def close(self):
        if self._open:
            cv2.destroyWindow(self._window)
            self._open = False

    def get_mapped_rotations(self, cam_rotations: Dict[str, list]) -> Dict[str, list]:
        """Apply mapping + gain. Returns {model_bone: quat}"""
        out = {}
        for cam_b, model_b in self.mapping.items():
            if cam_b in cam_rotations:
                gain = self.gains.get(cam_b, 1.0)
                quat = cam_rotations[cam_b]
                from scipy.spatial.transform import Rotation as R
                rv = R.from_quat(quat).as_rotvec() * gain
                out[model_b] = R.from_rotvec(rv).as_quat().tolist()
        return out

    # ── rendering ────────────────────────────────────────────────────────────

    def render(self):
        if not self._open:
            return
        p = np.full((self.PANEL_H, self.PANEL_W, 3), 28, dtype=np.uint8)
        self._draw_header(p)
        self._draw_columns(p)
        self._draw_connections(p)
        self._draw_sliders(p)
        self._panel = p
        cv2.imshow(self._window, p)

    def _draw_header(self, p):
        cv2.putText(p, "Camera bones", (self.PAD_X, 38), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100,220,180), 1)
        cv2.putText(p, "Model bones", (self.PAD_X + self.COL_W + 60, 38), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100,160,240), 1)

    def _cam_bone_rect(self, idx) -> Tuple[int,int,int,int]:
        x = self.PAD_X
        y = self.PAD_Y + idx * self.ROW_H
        return (x, y, self.COL_W, self.ROW_H - 4)

    def _model_bone_rect(self, idx) -> Tuple[int,int,int,int]:
        x = self.PAD_X + self.COL_W + 60
        y = self.PAD_Y + idx * self.ROW_H
        return (x, y, self.COL_W, self.ROW_H - 4)

    def _draw_columns(self, p):
        for i, name in enumerate(self.camera_bones):
            x,y,w,h = self._cam_bone_rect(i)
            color = (60,180,120) if name == self._selected_cam else (40,120,80)
            mapped = name in self.mapping
            if mapped: color = (30,200,100)
            cv2.rectangle(p, (x,y), (x+w, y+h), color, -1)
            cv2.putText(p, name[:22], (x+6, y+h//2+5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220,255,220), 1)

        for i, name in enumerate(self.model_bones[:20]):  # cap display 
            x,y,w,h = self._model_bone_rect(i)
            mapped = name in self.mapping.values()
            color = (40,80,160) if not mapped else (30,100,200)
            cv2.rectangle(p, (x,y), (x+w, y+h), color, -1)
            cv2.putText(p, name[:22], (x+6, y+h//2+5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200,220,255), 1)

    def _draw_connections(self, p):
        for cam_b, model_b in self.mapping.items():
            if cam_b in self.camera_bones and model_b in self.model_bones:
                ci = self.camera_bones.index(cam_b)
                mi = self.model_bones.index(model_b)
                cx,cy,cw,ch = self._cam_bone_rect(ci)
                mx,my,mw,mh = self._model_bone_rect(mi)
                pt1 = (cx+cw, cy+ch//2)
                pt2 = (mx,    my+mh//2)
                cv2.line(p, pt1, pt2, (255,200,50), 1, cv2.LINE_AA)

    def _slider_y(self, idx) -> int:
        base = self.PAD_Y + max(len(self.camera_bones), 8) * self.ROW_H + 20
        return base + idx * 32

    def _draw_sliders(self, p):
        cv2.putText(p, "Gain per bone", (self.PAD_X, self._slider_y(0) - 8), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180,180,180), 1)
        for idx, (cam_b, _model_b) in enumerate(self.mapping.items()):
            y = self._slider_y(idx)
            gain = self.gains.get(cam_b, 1.0)
            # track
            cv2.rectangle(p, (self.PAD_X, y+8), (self.PANEL_W-20, y+14), (60,60,60), -1)
            # fill
            fill_x = int(self.PAD_X + (gain / 3.0) * (self.PANEL_W - 40 - self.PAD_X))
            cv2.rectangle(p, (self.PAD_X, y+8), (fill_x, y+14), (100,180,255), -1)
            # thumb
            cv2.circle(p, (fill_x, y+11), 7, (200,220,255), -1)
            cv2.putText(p, f"{cam_b}: {gain:.2f}", (self.PAD_X, y+5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180,180,180), 1)

    # ── mouse ────────────────────────────────────────────────────────────────

    def _on_mouse(self, event, mx, my, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            # Check cam column
            for i, name in enumerate(self.camera_bones):
                x,y,w,h = self._cam_bone_rect(i)
                if x <= mx <= x+w and y <= my <= y+h:
                    self._selected_cam = name
                    return
            # Check model column
            for i, name in enumerate(self.model_bones[:20]):
                x,y,w,h = self._model_bone_rect(i)
                if x <= mx <= x+w and y <= my <= y+h:
                    if self._selected_cam:
                        self.mapping[self._selected_cam] = name
                        self._selected_cam = None
                    return
            # Check sliders
            for idx, (cam_b, _) in enumerate(list(self.mapping.items())):
                y = self._slider_y(idx)
                if y+4 <= my <= y+18 and self.PAD_X <= mx <= self.PANEL_W-20:
                    self._drag_slider = cam_b

        elif event == cv2.EVENT_MOUSEMOVE and self._drag_slider:
            track_w = self.PANEL_W - 40 - self.PAD_X
            val = np.clip((mx - self.PAD_X) / track_w * 3.0, 0.1, 3.0)
            self.gains[self._drag_slider] = round(val, 2)

        elif event == cv2.EVENT_LBUTTONUP:
            self._drag_slider = None


class VTuberGUI:
    def __init__(self, on_import_vrm=None, on_import_fbx=None, on_calibrate=None):
        self.on_import_vrm = on_import_vrm
        self.on_import_fbx = on_import_fbx
        self.on_calibrate  = on_calibrate
        self._running = True
        self.bone_mapper_ui = BoneMappingUI()
        print("[GUI] OpenCV window mode + BoneMapper panel")

    def setup(self):
        pass

    def open_bone_mapper(self):
        self.bone_mapper_ui.open()

    def update_preview(self, frame_rgba):
        pass

    def render_frame(self):
        self.bone_mapper_ui.render()

    def is_running(self) -> bool:
        return self._running

    def set_running(self, val: bool):
        self._running = val

    def cleanup(self):
        self.bone_mapper_ui.close()
        cv2.destroyAllWindows()
