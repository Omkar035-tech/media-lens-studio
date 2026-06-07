import os
import platform

# Help pyassimp find the system library, especially on Apple Silicon Macs
if platform.system() == "Darwin":
    # Common Homebrew paths for Apple Silicon
    brew_lib_path = "/opt/homebrew/lib"
    if os.path.exists(brew_lib_path):
        # pyassimp's helper looks at LD_LIBRARY_PATH on posix systems
        if "LD_LIBRARY_PATH" in os.environ:
            os.environ["LD_LIBRARY_PATH"] += ":" + brew_lib_path
        else:
            os.environ["LD_LIBRARY_PATH"] = brew_lib_path
        
        # Also set ASSIMP_LIBRARY_PATH just in case of newer versions
        os.environ["ASSIMP_LIBRARY_PATH"] = brew_lib_path

try:
    import pyassimp
    PYASSIMP_AVAILABLE = True
except Exception as e:
    print(f"[FBX] Warning: pyassimp or assimp library not found. FBX support disabled. {e}")
    PYASSIMP_AVAILABLE = False

import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import Dict, List, Optional

class FBXSupport:
    def __init__(self):
        self.scene = None
        self.bone_nodes: Dict[str, any] = {}  # name → assimp node
        self.available = PYASSIMP_AVAILABLE

    def load_fbx(self, file_path: str) -> bool:
        if not self.available:
            print("[FBX] Error: Cannot load FBX because assimp library is missing.")
            return False
        try:
            if self.scene:
                pyassimp.release(self.scene)
            self.scene = pyassimp.load(file_path)
            self.bone_nodes = {}
            self._walk(self.scene.rootnode)
            print(f"[FBX] Loaded {file_path} — {len(self.bone_nodes)} nodes found")
            return True
        except Exception as e:
            print(f"[FBX] Load error: {e}")
            return False

    def _walk(self, node):
        self.bone_nodes[node.name] = node
        for child in node.children:
            self._walk(child)

    def get_bone_names(self) -> List[str]:
        """Return all node names — used to populate the UI sidebar."""
        if not self.scene:
            return []
        return sorted(self.bone_nodes.keys())

    def apply_rotations(self, rotations: Dict[str, List[float]]):
        """rotations: {bone_name: [x,y,z,w] quaternion}"""
        if not self.scene or not self.available:
            return
        for bone_name, q_list in rotations.items():
            node = self.bone_nodes.get(bone_name)
            if node is None:
                continue
            # Convert quat to 4x4 rotation matrix
            r = R.from_quat(q_list)  # [x,y,z,w]
            rot_mat = r.as_matrix()
            # Preserve existing translation from node's transformation
            t = node.transformation
            # Build new 4x4: keep translation column, replace rotation 3x3
            new_transform = np.array(t, dtype=np.float32).copy()
            new_transform[:3, :3] = rot_mat.astype(np.float32)
            node.transformation = new_transform

    def close(self):
        if self.scene and self.available:
            pyassimp.release(self.scene)
            self.scene = None
