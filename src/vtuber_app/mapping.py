import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any, Optional, List, Tuple
from .smoothing import OneEuroFilter, MultiOneEuroFilter

class HeadPoseEstimator:
    def __init__(self):
        # 6 canonical face landmarks (Indices for MediaPipe 478-point mesh)
        # nose tip=1, chin=152, left eye outer=33, right eye outer=263, left mouth=61, right mouth=291
        self.indices = [1, 152, 33, 263, 61, 291]
        
        # Known 3D positions in a neutral face mesh (metric meters)
        self.model_pts = np.array([
            (0.0, 0.0, 0.0),          # Nose tip
            (0.0, -0.09, -0.03),      # Chin
            (-0.045, 0.045, -0.03),   # Left eye outer corner
            (0.045, 0.045, -0.03),    # Right eye outer corner
            (-0.03, -0.035, -0.02),   # Left mouth corner
            (0.03, -0.035, -0.02)     # Right mouth corner
        ], dtype=np.float64)
        
        self.R_neutral_inv = np.eye(3)
        self.is_calibrated = False

    def calibrate(self, face_landmarks, img_w, img_h):
        if not face_landmarks: return
        R_current = self._estimate_absolute_matrix(face_landmarks[0], img_w, img_h)
        if R_current is not None:
            self.R_neutral_inv = np.linalg.inv(R_current)
            self.is_calibrated = True

    def _estimate_absolute_matrix(self, lms, img_w, img_h):
        img_pts = np.array([
            (lms[i].x * img_w, lms[i].y * img_h) for i in self.indices
        ], dtype=np.float64)
        
        focal = img_w
        cam_matrix = np.array([
            [focal, 0, img_w / 2],
            [0, focal, img_h / 2],
            [0, 0, 1]
        ], dtype=np.float64)
        
        dist_coeffs = np.zeros((4, 1))
        success, rvec, tvec = cv2.solvePnP(self.model_pts, img_pts, cam_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE)
        
        if success:
            R_mat, _ = cv2.Rodrigues(rvec)
            return R_mat
        return None

    def estimate(self, face_landmarks, img_w, img_h, head_gain=1.0) -> Dict[str, List[float]]:
        if not face_landmarks: return {}
        
        R_current = self._estimate_absolute_matrix(face_landmarks[0], img_w, img_h)
        if R_current is None: return {}
        
        R_delta = self.R_neutral_inv @ R_current
        rot = R.from_matrix(R_delta)
        
        # Apply 40% to neck, 60% to head
        # Use rotvec for proportional rotation (equivalent to slerp from identity)
        rot_vec = rot.as_rotvec() * head_gain
        neck_rot = R.from_rotvec(rot_vec * 0.4).as_quat().tolist()
        head_rot = R.from_rotvec(rot_vec * 0.6).as_quat().tolist()
        
        return {
            "neck": neck_rot,
            "head": head_rot
        }

class BlendshapeMapper:
    def __init__(self):
        self.filters = {
            "eyeBlinkLeft": OneEuroFilter(min_cutoff=1.0, beta=0.3),
            "eyeBlinkRight": OneEuroFilter(min_cutoff=1.0, beta=0.3),
            "jawOpen": OneEuroFilter(min_cutoff=1.0, beta=0.3)
        }

    def map(self, face_landmarks, timestamp) -> Dict[str, float]:
        if not face_landmarks: return {"eyeBlinkLeft": 0.0, "eyeBlinkRight": 0.0, "jawOpen": 0.0}
        lms = face_landmarks[0]
        
        # Vertical / horizontal distance ratios
        def eye_ratio(top, bottom, left, right):
            v = np.linalg.norm(np.array([lms[top].x - lms[bottom].x, lms[top].y - lms[bottom].y]))
            h = np.linalg.norm(np.array([lms[left].x - lms[right].x, lms[left].y - lms[right].y]))
            return v / (h + 1e-6)

        # left eye: 159, 145, 33, 133
        ear_l = eye_ratio(159, 145, 33, 133)
        # right eye: 386, 374, 362, 263
        ear_r = eye_ratio(386, 374, 362, 263)
        
        # Normalize: 0=open (ear ~0.3), 1=closed (ear ~0.1)
        blink_l = np.clip(1.0 - (ear_l - 0.1) / 0.2, 0.0, 1.0)
        blink_r = np.clip(1.0 - (ear_r - 0.1) / 0.2, 0.0, 1.0)
        
        # Jaw open: 13 to 14 vs face height 10 to 152
        v_gap = abs(lms[13].y - lms[14].y)
        f_h = abs(lms[10].y - lms[152].y)
        jaw = np.clip(v_gap / (f_h * 0.2 + 1e-6), 0.0, 1.0)
        
        return {
            "eyeBlinkLeft": self.filters["eyeBlinkLeft"].update(float(blink_l), timestamp),
            "eyeBlinkRight": self.filters["eyeBlinkRight"].update(float(blink_r), timestamp),
            "jawOpen": self.filters["jawOpen"].update(float(jaw), timestamp)
        }

class BodyIKSolver:
    def __init__(self):
        self.neutral_world_lms = None

    def calibrate(self, world_landmarks):
        if world_landmarks:
            self.neutral_world_lms = world_landmarks[0]

    def _solve_2bone_ik(self, s, e, w, rest_dir):
        """
        s: shoulder pos (numpy)
        e: elbow pos
        w: wrist target pos
        rest_dir: vector from shoulder to elbow in rest pose
        """
        # Vector from shoulder to wrist
        sw = w - s
        dist_sw = np.linalg.norm(sw)
        
        # Bone lengths
        a = np.linalg.norm(e - s) # upper arm
        b = np.linalg.norm(w - e) # lower arm
        
        # Elbow angle (law of cosines)
        # c^2 = a^2 + b^2 - 2ab*cos(theta)
        cos_theta = (a**2 + b**2 - dist_sw**2) / (2 * a * b + 1e-6)
        elbow_angle = np.arccos(np.clip(cos_theta, -1.0, 1.0))
        # Bend angle relative to straight arm is pi - elbow_angle
        bend_angle = np.pi - elbow_angle
        
        # Shoulder rotation: align rest_dir to sw
        # We need a quaternion that rotates rest_dir to sw
        # Using scipy.spatial.transform.Rotation.align_vectors or manually
        sw_norm = sw / (dist_sw + 1e-6)
        rest_norm = np.array(rest_dir) / (np.linalg.norm(rest_dir) + 1e-6)
        
        # Find rotation axis (cross product)
        axis = np.cross(rest_norm, sw_norm)
        axis_len = np.linalg.norm(axis)
        if axis_len < 1e-6:
            # Parallel or anti-parallel
            dot = np.dot(rest_norm, sw_norm)
            if dot < -0.99:
                # Anti-parallel: find any orthogonal axis
                ortho = np.array([1, 0, 0]) if abs(rest_norm[0]) < 0.9 else np.array([0, 1, 0])
                axis = np.cross(rest_norm, ortho)
                axis /= np.linalg.norm(axis)
                shoulder_rot = R.from_rotvec(axis * np.pi)
            else:
                shoulder_rot = R.identity()
        else:
            axis /= axis_len
            angle = np.arccos(np.clip(np.dot(rest_norm, sw_norm), -1.0, 1.0))
            shoulder_rot = R.from_rotvec(axis * angle)

        # Elbow rotation: simple bend around local axis
        # Compute bend axis (perpendicular to plane S-E-W)
        v_se = e - s
        v_ew = w - e
        bend_axis = np.cross(v_se, v_ew)
        bend_axis_len = np.linalg.norm(bend_axis)
        if bend_axis_len < 1e-6:
            # Collinear, pick a default axis (usually perpendicular to rest_dir)
            bend_axis = np.array([0, 0, 1])
        else:
            bend_axis /= bend_axis_len
            
        elbow_rot = R.from_rotvec(bend_axis * bend_angle)
        
        return shoulder_rot.as_quat().tolist(), elbow_rot.as_quat().tolist()

    def solve(self, world_landmarks) -> Dict[str, List[float]]:
        if not world_landmarks: return {}
        lms = world_landmarks[0]
        
        rots = {}
        
        # Spine rotation (mid-hip to mid-shoulder)
        hip_mid = np.array([(lms[23].x + lms[24].x)/2, (lms[23].y + lms[24].y)/2, (lms[23].z + lms[24].z)/2])
        sh_mid  = np.array([(lms[11].x + lms[12].x)/2, (lms[11].y + lms[12].y)/2, (lms[11].z + lms[12].z)/2])
        
        spine_vec = sh_mid - hip_mid
        up = np.array([0, 1, 0])
        # Calculate angle between spine_vec and up
        v1 = spine_vec / (np.linalg.norm(spine_vec) + 1e-6)
        angle = np.arccos(np.clip(np.dot(v1, up), -1.0, 1.0))
        axis = np.cross(up, v1)
        axis_len = np.linalg.norm(axis)
        if axis_len > 1e-6:
            axis /= axis_len
            # Limit spine rotation
            angle = np.clip(angle, -np.radians(25), np.radians(25))
            rots["spine"] = R.from_rotvec(axis * angle * 0.5).as_quat().tolist()
            rots["chest"] = R.from_rotvec(axis * angle * 0.5).as_quat().tolist()

        # Arm IK
        def get_pt(i): return np.array([lms[i].x, lms[i].y, lms[i].z])
        
        # Left Arm
        if lms[11].visibility > 0.6 and lms[13].visibility > 0.6 and lms[15].visibility > 0.6:
            s, e, w = get_pt(11), get_pt(13), get_pt(15)
            # VRM left arm rest pose is usually along -X
            u, l = self._solve_2bone_ik(s, e, w, [-1, 0, 0])
            rots["leftUpperArm"] = u
            rots["leftLowerArm"] = l
            
        # Right Arm
        if lms[12].visibility > 0.6 and lms[14].visibility > 0.6 and lms[16].visibility > 0.6:
            s, e, w = get_pt(12), get_pt(14), get_pt(16)
            # VRM right arm rest pose is usually along +X
            u, l = self._solve_2bone_ik(s, e, w, [1, 0, 0])
            rots["rightUpperArm"] = u
            rots["rightLowerArm"] = l
            
        return rots

class BoneApplicator:
    def __init__(self):
        self.rest_poses: Dict[str, R] = {}
        self.filters: Dict[str, MultiOneEuroFilter] = {}

    def set_rest_poses(self, poses: Dict[str, List[float]]):
        for name, q in poses.items():
            self.rest_poses[name] = R.from_quat(q)

    def apply(self, delta_quats: Dict[str, List[float]], timestamp) -> Dict[str, List[float]]:
        final_rots = {}
        for name, dq_list in delta_quats.items():
            if name in self.rest_poses:
                dq = R.from_quat(dq_list)
                # final = rest * delta
                final = self.rest_poses[name] * dq
                
                # Filter quaternion components
                if name not in self.filters:
                    self.filters[name] = MultiOneEuroFilter(4, min_cutoff=1.0, beta=0.3)
                
                smoothed_q = self.filters[name](final.as_quat().tolist(), timestamp)
                # Renormalize
                q_norm = np.linalg.norm(smoothed_q)
                if q_norm > 1e-9:
                    smoothed_q = [s/q_norm for s in smoothed_q]
                
                final_rots[name] = smoothed_q
        return final_rots

class BoneMapper:
    """Legacy class wrapper to maintain compatibility with main.py if needed, 
    but we should transition to the new classes."""
    def __init__(self):
        self.head_estimator = HeadPoseEstimator()
        self.body_solver = BodyIKSolver()
        self.bone_applicator = BoneApplicator()

    def set_rest_poses(self, poses):
        self.bone_applicator.set_rest_poses(poses)

    def calibrate(self, result, img_w, img_h):
        if result.face_landmarks:
            self.head_estimator.calibrate(result.face_landmarks, img_w, img_h)
        if result.pose_world_landmarks:
            self.body_solver.calibrate(result.pose_world_landmarks)

    def map_all(self, result, img_w, img_h, timestamp) -> Dict[str, List[float]]:
        deltas = {}
        
        # Head/Neck
        if result.face_landmarks:
            deltas.update(self.head_estimator.estimate(result.face_landmarks, img_w, img_h))
            
        # Body
        if result.pose_world_landmarks:
            deltas.update(self.body_solver.solve(result.pose_world_landmarks))
            
        # Apply deltas to rest pose
        return self.bone_applicator.apply(deltas, timestamp)
