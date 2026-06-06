import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any, Optional


class BlendshapeMapper:
    LEFT_EYE  = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]

    def _ear(self, lms, idx):
        def pt(i): return np.array([lms[i].x, lms[i].y], dtype=np.float64)
        v1 = np.linalg.norm(pt(idx[1]) - pt(idx[5]))
        v2 = np.linalg.norm(pt(idx[2]) - pt(idx[4]))
        h  = np.linalg.norm(pt(idx[0]) - pt(idx[3]))
        return (v1 + v2) / (2.0 * h + 1e-6)

    def map_face(self, face_landmarks_list) -> Dict[str, float]:
        if not face_landmarks_list:
            return {"eyeBlinkLeft": 0.0, "eyeBlinkRight": 0.0, "jawOpen": 0.0}

        lms = face_landmarks_list[0]

        left_ear  = self._ear(lms, self.LEFT_EYE)
        right_ear = self._ear(lms, self.RIGHT_EYE)

        blink_l = float(np.clip(1.0 - (left_ear  - 0.15) / 0.15, 0.0, 1.0))
        blink_r = float(np.clip(1.0 - (right_ear - 0.15) / 0.15, 0.0, 1.0))

        upper = np.array([lms[13].x, lms[13].y], dtype=np.float64)
        lower = np.array([lms[14].x, lms[14].y], dtype=np.float64)
        jaw   = float(np.clip(np.linalg.norm(upper - lower) * 10.0, 0.0, 1.0))

        return {"eyeBlinkLeft": blink_l, "eyeBlinkRight": blink_r, "jawOpen": jaw}

    def estimate_head_pose(self, face_landmarks_list, img_w, img_h):
        if not face_landmarks_list:
            return [0.0, 0.0, 0.0, 1.0]
        lms = face_landmarks_list[0]

        model_pts = np.array([
            (0.0,    0.0,    0.0),
            (0.0,  -330.0, -65.0),
            (-225.0, 170.0,-135.0),
            ( 225.0, 170.0,-135.0),
            (-150.0,-150.0,-125.0),
            ( 150.0,-150.0,-125.0),
        ], dtype=np.float64)

        img_pts = np.array([
            (lms[1].x   * img_w, lms[1].y   * img_h),
            (lms[152].x * img_w, lms[152].y * img_h),
            (lms[33].x  * img_w, lms[33].y  * img_h),
            (lms[263].x * img_w, lms[263].y * img_h),
            (lms[61].x  * img_w, lms[61].y  * img_h),
            (lms[291].x * img_w, lms[291].y * img_h),
        ], dtype=np.float64)

        focal = float(img_w)
        cam   = np.array([[focal, 0, img_w/2],
                          [0, focal, img_h/2],
                          [0, 0, 1]], dtype=np.float64)
        ok, rvec, _ = cv2.solvePnP(model_pts, img_pts, cam, np.zeros((4,1)),
                                   flags=cv2.SOLVEPNP_ITERATIVE)
        if ok:
            return R.from_rotvec(rvec.flatten()).as_quat().tolist()
        return [0.0, 0.0, 0.0, 1.0]


class BoneMapper:
    def _vec(self, p1, p2) -> np.ndarray:
        return np.array([p2.x - p1.x, p2.y - p1.y, p2.z - p1.z], dtype=np.float64)

    def _v2q(self, target, source=(0.0, -1.0, 0.0)):
        # explicit float64 dtype fixes the numpy casting error
        t = np.array(target, dtype=np.float64)
        s = np.array(source, dtype=np.float64)

        tn = np.linalg.norm(t)
        sn = np.linalg.norm(s)
        if tn < 1e-9 or sn < 1e-9:
            return [0.0, 0.0, 0.0, 1.0]

        t /= tn
        s /= sn

        ax = np.cross(s, t)
        ax_norm = np.linalg.norm(ax)
        if ax_norm < 1e-6:
            return [0.0, 0.0, 0.0, 1.0]

        ax /= ax_norm
        angle = np.arccos(np.clip(np.dot(s, t), -1.0, 1.0))
        return R.from_rotvec(ax * angle).as_quat().tolist()

    def map_pose(self, pose_landmarks_list) -> Dict[str, Any]:
        if not pose_landmarks_list:
            return {}

        lms = pose_landmarks_list[0]
        if len(lms) < 25:
            return {}

        rots = {}

        # Only map bones where both landmarks are visible enough
        def vis(i): return getattr(lms[i], 'visibility', 1.0) > 0.4

        if vis(11) and vis(13):
            rots["leftUpperArm"]  = self._v2q(self._vec(lms[11], lms[13]))
        if vis(12) and vis(14):
            rots["rightUpperArm"] = self._v2q(self._vec(lms[12], lms[14]))

        if vis(11) and vis(12) and vis(23) and vis(24):
            sh_mid = np.array([(lms[11].x+lms[12].x)/2,
                               (lms[11].y+lms[12].y)/2,
                               (lms[11].z+lms[12].z)/2], dtype=np.float64)
            hp_mid = np.array([(lms[23].x+lms[24].x)/2,
                               (lms[23].y+lms[24].y)/2,
                               (lms[23].z+lms[24].z)/2], dtype=np.float64)
            rots["spine"] = self._v2q(sh_mid - hp_mid, (0.0, 1.0, 0.0))

        return rots