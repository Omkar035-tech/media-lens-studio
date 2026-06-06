import pyassimp
import numpy as np
from typing import Dict, List, Any

class FBXSupport:
    def __init__(self):
        self.scene = None
        self.bone_nodes = {} # Bone name -> node object
        self.mapping = {
            "leftUpperArm": "mixamorig:LeftArm",
            "rightUpperArm": "mixamorig:RightArm",
            "spine": "mixamorig:Spine"
        } # Default Mixamo mapping

    def load_fbx(self, file_path):
        self.scene = pyassimp.load(file_path)
        self._find_bones(self.scene.rootnode)
        return self.scene

    def _find_bones(self, node):
        # In assimp, bones are just nodes in the hierarchy
        # We can identify them by name or by checking if they are referenced in meshes
        self.bone_nodes[node.name] = node
        for child in node.children:
            self._find_bones(child)

    def apply_rotations(self, rotations: Dict[str, List[float]]):
        if not self.scene:
            return
            
        for bone_name, quat in rotations.items():
            fbx_bone_name = self.mapping.get(bone_name)
            if fbx_bone_name in self.bone_nodes:
                node = self.bone_nodes[fbx_bone_name]
                # node.transformation needs to be updated with the rotation
                # Assimp uses 4x4 matrices for transformations
                # This would involve converting quat to matrix and updating node.transformation
                pass

    def close(self):
        if self.scene:
            pyassimp.release(self.scene)
