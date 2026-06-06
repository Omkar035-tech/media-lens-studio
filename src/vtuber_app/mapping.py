import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any, List

class BlendshapeMapper:
    def __init__(self):
        # Indices for EAR calculation
        self.LEFT_EYE = [33, 160, 158, 133, 153, 144]
        self.RIGHT_EYE = [362, 385, 387, 263, 373, 380]
        self.MOUTH = [13, 14, 78, 308] # Inner lips and corners
        
    def calculate_ear(self, landmarks, eye_indices):
        # Vertical distances
        v1 = np.linalg.norm(np.array([landmarks[eye_indices[1]].x, landmarks[eye_indices[1]].y]) - 
                            np.array([landmarks[eye_indices[5]].x, landmarks[eye_indices[5]].y]))
        v2 = np.linalg.norm(np.array([landmarks[eye_indices[2]].x, landmarks[eye_indices[2]].y]) - 
                            np.array([landmarks[eye_indices[4]].x, landmarks[eye_indices[4]].y]))
        # Horizontal distance
        h = np.linalg.norm(np.array([landmarks[eye_indices[0]].x, landmarks[eye_indices[0]].y]) - 
                           np.array([landmarks[eye_indices[3]].x, landmarks[eye_indices[3]].y]))
        ear = (v1 + v2) / (2.0 * h)
        return ear

    def map_face(self, face_landmarks) -> Dict[str, float]:
        if not face_landmarks:
            return {}
            
        landmarks = face_landmarks.landmark
        
        # Blinks
        left_ear = self.calculate_ear(landmarks, self.LEFT_EYE)
        right_ear = self.calculate_ear(landmarks, self.RIGHT_EYE)
        
        # Simple thresholding/scaling for blink weight (0.2 is roughly closed)
        eyeBlinkLeft = np.clip(1.0 - (left_ear - 0.15) / (0.3 - 0.15), 0, 1)
        eyeBlinkRight = np.clip(1.0 - (right_ear - 0.15) / (0.3 - 0.15), 0, 1)
        
        # Mouth open (jawOpen)
        upper_lip = np.array([landmarks[13].x, landmarks[13].y])
        lower_lip = np.array([landmarks[14].x, landmarks[14].y])
        mouth_open = np.linalg.norm(upper_lip - lower_lip)
        jawOpen = np.clip(mouth_open * 10, 0, 1) # Scaling factor
        
        return {
            "eyeBlinkLeft": float(eyeBlinkLeft),
            "eyeBlinkRight": float(eyeBlinkRight),
            "jawOpen": float(jawOpen)
        }

    def estimate_head_pose(self, face_landmarks, img_w, img_h):
        # 3D model points (simplified)
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left Mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ])

        # 2D image points from landmarks
        landmarks = face_landmarks.landmark
        image_points = np.array([
            (landmarks[1].x * img_w, landmarks[1].y * img_h),     # Nose tip
            (landmarks[152].x * img_w, landmarks[152].y * img_h), # Chin
            (landmarks[33].x * img_w, landmarks[33].y * img_h),   # Left eye left corner
            (landmarks[263].x * img_w, landmarks[263].y * img_h), # Right eye right corner
            (landmarks[61].x * img_w, landmarks[61].y * img_h),   # Left Mouth corner
            (landmarks[291].x * img_w, landmarks[291].y * img_h)  # Right mouth corner
        ], dtype="double")

        focal_length = img_w
        center = (img_w / 2, img_h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype="double")

        dist_coeffs = np.zeros((4, 1)) # Assuming no lens distortion
        (success, rotation_vector, translation_vector) = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if success:
            r = R.from_rotvec(rotation_vector.flatten())
            return r.as_quat()
        return [0, 0, 0, 1]

class BoneMapper:
    def __init__(self):
        pass

    def get_vector(self, p1, p2):
        return np.array([p2.x - p1.x, p2.y - p1.y, p2.z - p1.z])

    def map_pose(self, pose_landmarks) -> Dict[str, Any]:
        if not pose_landmarks:
            return {}
            
        # Landmark indices
        # L_SHOULDER = 11, R_SHOULDER = 12
        # L_ELBOW = 13, R_ELBOW = 14
        # L_WRIST = 15, R_WRIST = 16
        # L_HIP = 23, R_HIP = 24
        
        landmarks = pose_landmarks
        
        rotations = {}
        
        # Left Upper Arm
        v_l_arm = self.get_vector(landmarks[11], landmarks[13])
        rotations["leftUpperArm"] = self.vector_to_quat(v_l_arm, [0, -1, 0]) # Assuming default bone is down
        
        # Right Upper Arm
        v_r_arm = self.get_vector(landmarks[12], landmarks[14])
        rotations["rightUpperArm"] = self.vector_to_quat(v_r_arm, [0, -1, 0])
        
        # Spine lean (shoulders relative to hips)
        shoulder_mid = np.array([
            (landmarks[11].x + landmarks[12].x) / 2,
            (landmarks[11].y + landmarks[12].y) / 2,
            (landmarks[11].z + landmarks[12].z) / 2
        ])
        hip_mid = np.array([
            (landmarks[23].x + landmarks[24].x) / 2,
            (landmarks[23].y + landmarks[24].y) / 2,
            (landmarks[23].z + landmarks[24].z) / 2
        ])
        v_spine = shoulder_mid - hip_mid
        rotations["spine"] = self.vector_to_quat(v_spine, [0, 1, 0])
        
        return rotations

    def vector_to_quat(self, target_v, source_v=[0, 1, 0]):
        # Normalize vectors
        target_v = target_v / np.linalg.norm(target_v)
        source_v = np.array(source_v) / np.linalg.norm(source_v)
        
        # Cross product to find axis of rotation
        axis = np.cross(source_v, target_v)
        axis_norm = np.linalg.norm(axis)
        
        if axis_norm < 1e-6:
            return [0, 0, 0, 1]
            
        axis = axis / axis_norm
        
        # Dot product to find angle
        angle = np.arccos(np.clip(np.dot(source_v, target_v), -1.0, 1.0))
        
        r = R.from_rotvec(axis * angle)
        return r.as_quat()
