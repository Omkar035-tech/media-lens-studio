import cv2
import numpy as np

class EyeOverlay:
    def __init__(self):
        # MediaPipe indices for eye regions
        self.LEFT_EYE_INDICES = [33, 133, 160, 144, 158, 153]
        self.RIGHT_EYE_INDICES = [362, 263, 387, 373, 385, 380]
        self.TARGET_SIZE = (64, 32)

    def extract_eye_texture(self, frame, face_landmarks):
        if not face_landmarks:
            return None, None
            
        h, w, _ = frame.shape
        landmarks = face_landmarks.landmark
        
        left_eye_pts = np.array([(landmarks[i].x * w, landmarks[i].y * h) for i in self.LEFT_EYE_INDICES], dtype=np.float32)
        right_eye_pts = np.array([(landmarks[i].x * w, landmarks[i].y * h) for i in self.RIGHT_EYE_INDICES], dtype=np.float32)
        
        left_eye_tex = self._warp_to_ellipse(frame, left_eye_pts)
        right_eye_tex = self._warp_to_ellipse(frame, right_eye_pts)
        
        return left_eye_tex, right_eye_tex

    def _warp_to_ellipse(self, frame, points):
        # Calculate bounding box
        x, y, w, h = cv2.boundingRect(points)
        roi = frame[y:y+h, x:x+w]
        
        if roi.size == 0:
            return None
            
        # Warp to target size (64x32)
        warped = cv2.resize(roi, self.TARGET_SIZE)
        
        # Apply elliptical mask
        mask = np.zeros(self.TARGET_SIZE[::-1], dtype=np.uint8)
        cv2.ellipse(mask, (self.TARGET_SIZE[0]//2, self.TARGET_SIZE[1]//2), 
                    (self.TARGET_SIZE[0]//2, self.TARGET_SIZE[1]//2), 0, 0, 360, 255, -1)
        
        result = cv2.bitwise_and(warped, warped, mask=mask)
        return result
