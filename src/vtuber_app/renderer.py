# import os
# import json
# import time
# import io
# import glfw
# import glm
# import numpy as np
# from OpenGL.GL import *
# from pygltflib import GLTF2
# from PIL import Image
# from typing import Dict, Any, List, Optional, Tuple
# from .shader_utils import Shader

# # VRM 0.x Bone Names to Humanoid mapping
# VRM_BONE_MAP = {
#     "hips": "hips",
#     "spine": "spine",
#     "chest": "chest",
#     "neck": "neck",
#     "head": "head",
#     "leftUpperArm": "leftUpperArm",
#     "leftLowerArm": "leftLowerArm",
#     "rightUpperArm": "rightUpperArm",
#     "rightLowerArm": "rightLowerArm"
# }

# # GLSL Shaders
# VERTEX_SHADER = """
# #version 330 core
# layout (location = 0) in vec3 position;
# layout (location = 1) in vec3 normal;
# layout (location = 2) in vec2 texcoord;
# layout (location = 3) in ivec4 joints;
# layout (location = 4) in vec4 weights;

# uniform mat4 boneMatrices[128];
# uniform mat4 model;
# uniform mat4 view;
# uniform mat4 projection;

# out vec3 FragPos;
# out vec3 Normal;
# out vec2 TexCoord;

# void main() {
#     float totalWeight = weights.x + weights.y + weights.z + weights.w;
#     mat4 skinMatrix;
#     if (totalWeight > 0.01) {
#         skinMatrix = 
#             weights.x * boneMatrices[joints.x] +
#             weights.y * boneMatrices[joints.y] +
#             weights.z * boneMatrices[joints.z] +
#             weights.w * boneMatrices[joints.w];
#     } else {
#         skinMatrix = mat4(1.0);
#     }

#     vec4 worldPos = model * skinMatrix * vec4(position, 1.0);
#     FragPos = worldPos.xyz;
#     Normal = normalize(mat3(model * skinMatrix) * normal);
#     TexCoord = texcoord;
#     gl_Position = projection * view * worldPos;
# }
# """

# FRAGMENT_SHADER = """
# #version 330 core
# out vec4 FragColor;

# in vec3 FragPos;
# in vec3 Normal;
# in vec2 TexCoord;

# uniform vec4 baseColorFactor;
# uniform sampler2D baseColorTexture;
# uniform bool hasTexture;

# void main() {
#     vec3 lightDir = normalize(vec3(0.5, 1.0, 0.5));
#     float diff = max(dot(Normal, lightDir), 0.0);
#     vec3 ambient = vec3(0.4); 
#     vec3 diffuse = diff * vec3(0.6);
    
#     vec4 texColor = hasTexture ? texture(baseColorTexture, TexCoord) : vec4(1.0);
#     vec4 finalColor = texColor * baseColorFactor;
    
#     if (finalColor.a < 0.1) discard;
    
#     FragColor = vec4((ambient + diffuse) * finalColor.rgb, finalColor.a);
# }
# """

# class Node:
#     def __init__(self, index: int, name: str = ""):
#         self.index = index
#         self.name = name
#         self.parent: Optional[int] = None
#         self.children: List[int] = []
#         self.translation = glm.vec3(0.0)
#         self.rotation = glm.quat(1.0, 0.0, 0.0, 0.0)
#         self.scale = glm.vec3(1.0)
#         self.inverse_bind_matrix = glm.mat4(1.0)
#         self.global_matrix = glm.mat4(1.0)
#         self.skin_matrix = glm.mat4(1.0)

# class MeshPrimitive:
#     def __init__(self, mesh_index: int, primitive_index: int):
#         self.mesh_index = mesh_index
#         self.primitive_index = primitive_index
#         self.vao = 0
#         self.vbos = {}
#         self.indices_count = 0
#         self.material_index = -1
#         self.morph_targets = []
#         self.base_positions = None
#         self.current_positions = None
#         self.has_morphs = False

# class VRMRenderer:
#     def __init__(self):
#         self.window = None
#         self.shader = None
#         self.gltf: Optional[GLTF2] = None
#         self.nodes: List[Node] = []
#         self.mesh_primitives: List[MeshPrimitive] = []
#         self.textures: List[int] = []
#         self.bone_node_map: Dict[str, int] = {}
#         self.blendshape_groups: List[Dict] = []
#         self.active_blendshapes: Dict[str, float] = {}
#         self.should_close = False
#         self._binary_blob_cache: Optional[bytes] = None
        
#         self._init_glfw()
#         self.shader = Shader(VERTEX_SHADER, FRAGMENT_SHADER)
#         self.resize(640, 480)
        
#         self.view = glm.lookAt(glm.vec3(0, 1.4, 2.5), glm.vec3(0, 1.4, 0), glm.vec3(0, 1, 0))
#         self.projection = glm.perspective(glm.radians(30.0), 640/480, 0.05, 50.0)
#         self.model = glm.mat4(1.0)

#     def _init_glfw(self):
#         if not glfw.init():
#             raise Exception("Failed to initialize GLFW")
            
#         glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
#         glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
#         glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
#         glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
        
#         self.window = glfw.create_window(640, 480, "VRM Renderer", None, None)
#         if not self.window:
#             glfw.terminate()
#             raise Exception("Failed to create GLFW window")
        
#         print("[Renderer] GLFW window created (640x480)")
            
#         glfw.make_context_current(self.window)
        
#         self.root_vao = glGenVertexArrays(1)
#         glBindVertexArray(self.root_vao)
        
#         glEnable(GL_DEPTH_TEST)
#         glEnable(GL_BLEND)
#         glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

#     def load_vrm(self, path: str):
#         ext = os.path.splitext(path)[1].lower()
#         if ext == ".fbx":
#             print("[Renderer] Error: FBX not supported. Use .vrm or .glb")
#             return
#         if ext not in (".vrm", ".glb", ".gltf"):
#             print(f"[Renderer] Error: Unsupported format {ext}")
#             return

#         print(f"[Renderer] Loading Model: {path}")
#         self.vrm_dir = os.path.dirname(os.path.abspath(path))
#         self._binary_blob_cache = None

#         self.nodes = []
#         self.mesh_primitives = []
#         self.textures = []
#         self.bone_node_map = {}
#         self.blendshape_groups = []

#         try:
#             if ext in (".vrm", ".glb"):
#                 self.gltf = GLTF2().load_binary(path)
#             else:
#                 self.gltf = GLTF2().load(path)
#         except Exception as e:
#             print(f"[Renderer] Error loading file: {e}")
#             return

#         try:
#             self._binary_blob_cache = self.gltf.binary_blob()
#         except Exception:
#             self._binary_blob_cache = None

#         self._parse_nodes()
#         self._parse_skeleton()
#         self._parse_meshes()
#         self._parse_textures()
#         self._parse_blendshapes()
#         print("[Renderer] Model loaded successfully")

#     def _get_buffer_bytes(self, buffer_view_idx: int) -> bytes:
#         bv = self.gltf.bufferViews[buffer_view_idx]
#         buf = self.gltf.buffers[bv.buffer]
#         offset = bv.byteOffset or 0
#         length = bv.byteLength
#         if buf.uri is None:
#             if self._binary_blob_cache is None: return b""
#             return self._binary_blob_cache[offset: offset + length]
#         if buf.uri.startswith("data:"):
#             import base64
#             _, encoded = buf.uri.split(",", 1)
#             return base64.b64decode(encoded)[offset: offset + length]
#         with open(os.path.join(self.vrm_dir, buf.uri), "rb") as f:
#             f.seek(offset)
#             return f.read(length)

#     def _get_buffer_data(self, accessor_idx: int) -> np.ndarray:
#         accessor = self.gltf.accessors[accessor_idx]
#         dtype = {5120:np.int8, 5121:np.uint8, 5122:np.int16, 5123:np.uint16, 5125:np.uint32, 5126:np.float32}[accessor.componentType]
#         comps = {"SCALAR":1, "VEC2":2, "VEC3":3, "VEC4":4, "MAT4":16}[accessor.type]
#         raw = self._get_buffer_bytes(accessor.bufferView)
#         acc_off = accessor.byteOffset or 0
#         bv = self.gltf.bufferViews[accessor.bufferView]
#         stride = bv.byteStride or (np.dtype(dtype).itemsize * comps)
        
#         arr = np.zeros((accessor.count, comps), dtype=dtype)
#         for i in range(accessor.count):
#             start = acc_off + i * stride
#             arr[i] = np.frombuffer(raw[start:start + np.dtype(dtype).itemsize * comps], dtype=dtype)
#         return arr

#     def _parse_nodes(self):
#         self.nodes = []
#         for i, gn in enumerate(self.gltf.nodes):
#             node = Node(i, gn.name or "")
#             if gn.translation: node.translation = glm.vec3(*gn.translation)
#             if gn.rotation: node.rotation = glm.quat(gn.rotation[3], *gn.rotation[:3])
#             if gn.scale: node.scale = glm.vec3(*gn.scale)
#             if gn.children: node.children = list(gn.children)
#             self.nodes.append(node)
#         for i, node in enumerate(self.nodes):
#             for c in node.children: self.nodes[c].parent = i

#     def _parse_skeleton(self):
#         vrm_ext = self.gltf.extensions.get("VRM", {}) if self.gltf.extensions else {}
#         human_bones = vrm_ext.get("humanoid", {}).get("humanBones", [])
#         vrm_map = {b["bone"]: b["node"] for b in human_bones}
#         for vrm_n, int_n in VRM_BONE_MAP.items():
#             if int_n in vrm_map: self.bone_node_map[vrm_n] = vrm_map[int_n]
#         if self.gltf.skins:
#             skin = self.gltf.skins[0]
#             if skin.inverseBindMatrices is not None:
#                 ibm_data = self._get_buffer_data(skin.inverseBindMatrices)
#                 for i, jidx in enumerate(skin.joints):
#                     self.nodes[jidx].inverse_bind_matrix = glm.mat4(*ibm_data[i].astype(np.float32).tolist())

#     def _parse_meshes(self):
#         self.mesh_primitives = []
#         total_verts = 0
#         min_v, max_v = np.array([float('inf')]*3), np.array([float('-inf')]*3)
#         for midx, gm in enumerate(self.gltf.meshes):
#             for pidx, prim in enumerate(gm.primitives):
#                 mp = MeshPrimitive(midx, pidx)
#                 mp.material_index = prim.material if prim.material is not None else -1
#                 mp.vao = glGenVertexArrays(1)
#                 glBindVertexArray(mp.vao)
#                 at = prim.attributes
#                 if at.POSITION is not None:
#                     pos = self._get_buffer_data(at.POSITION).astype(np.float32)
#                     total_verts += len(pos)
#                     min_v = np.minimum(min_v, pos.min(axis=0))
#                     max_v = np.maximum(max_v, pos.max(axis=0))
#                     mp.base_positions = pos.copy()
#                     mp.current_positions = pos.copy()
#                     vbo = glGenBuffers(1)
#                     glBindBuffer(GL_ARRAY_BUFFER, vbo)
#                     glBufferData(GL_ARRAY_BUFFER, pos.nbytes, pos, GL_DYNAMIC_DRAW)
#                     glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
#                     glEnableVertexAttribArray(0)
#                     mp.vbos['POSITION'] = vbo
#                 if at.NORMAL is not None:
#                     norm = self._get_buffer_data(at.NORMAL).astype(np.float32)
#                     vbo = glGenBuffers(1)
#                     glBindBuffer(GL_ARRAY_BUFFER, vbo)
#                     glBufferData(GL_ARRAY_BUFFER, norm.nbytes, norm, GL_STATIC_DRAW)
#                     glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
#                     glEnableVertexAttribArray(1)
#                     mp.vbos['NORMAL'] = vbo
#                 if at.TEXCOORD_0 is not None:
#                     uv = self._get_buffer_data(at.TEXCOORD_0).astype(np.float32)
#                     vbo = glGenBuffers(1)
#                     glBindBuffer(GL_ARRAY_BUFFER, vbo)
#                     glBufferData(GL_ARRAY_BUFFER, uv.nbytes, uv, GL_STATIC_DRAW)
#                     glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 0, None)
#                     glEnableVertexAttribArray(2)
#                     mp.vbos['TEXCOORD_0'] = vbo
#                 if at.JOINTS_0 is not None:
#                     j = self._get_buffer_data(at.JOINTS_0).astype(np.int32)
#                     vbo = glGenBuffers(1)
#                     glBindBuffer(GL_ARRAY_BUFFER, vbo)
#                     glBufferData(GL_ARRAY_BUFFER, j.nbytes, j, GL_STATIC_DRAW)
#                     glVertexAttribIPointer(3, 4, GL_INT, 0, None)
#                     glEnableVertexAttribArray(3)
#                     mp.vbos['JOINTS_0'] = vbo
#                 if at.WEIGHTS_0 is not None:
#                     w = self._get_buffer_data(at.WEIGHTS_0).astype(np.float32)
#                     vbo = glGenBuffers(1)
#                     glBindBuffer(GL_ARRAY_BUFFER, vbo)
#                     glBufferData(GL_ARRAY_BUFFER, w.nbytes, w, GL_STATIC_DRAW)
#                     glVertexAttribPointer(4, 4, GL_FLOAT, GL_FALSE, 0, None)
#                     glEnableVertexAttribArray(4)
#                     mp.vbos['WEIGHTS_0'] = vbo
#                 if prim.indices is not None:
#                     idx = self._get_buffer_data(prim.indices).astype(np.uint32).flatten()
#                     mp.indices_count = len(idx)
#                     ebo = glGenBuffers(1)
#                     glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
#                     glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx, GL_STATIC_DRAW)
#                 if prim.targets:
#                     mp.has_morphs = True
#                     for t in prim.targets:
#                         pos_key = t.get("POSITION") if isinstance(t, dict) else getattr(t, "POSITION", None)
#                         if pos_key is not None: mp.morph_targets.append(self._get_buffer_data(pos_key).astype(np.float32))
#                 self.mesh_primitives.append(mp)
#                 glBindVertexArray(0)
#         print(f"[Renderer] Parsed {len(self.mesh_primitives)} primitives, {total_verts} vertices. BBox: {min_v} to {max_v}")

#     def _parse_textures(self):
#         self.textures = []
#         for tex in self.gltf.textures:
#             img = self.gltf.images[tex.source]
#             if img.uri and img.uri.startswith("data:"):
#                 import base64
#                 data = base64.b64decode(img.uri.split(",", 1)[1])
#             elif img.bufferView is not None:
#                 data = self._get_buffer_bytes(img.bufferView)
#             else:
#                 with open(os.path.join(self.vrm_dir, img.uri), "rb") as f: data = f.read()
            
#             pimg = Image.open(io.BytesIO(data)).convert("RGBA")
#             pdata = np.array(pimg, dtype=np.uint8)
#             tid = glGenTextures(1)
#             glBindTexture(GL_TEXTURE_2D, tid)
#             glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, pimg.width, pimg.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, pdata)
#             glGenerateMipmap(GL_TEXTURE_2D)
#             self.textures.append(tid)
#             print(f"[Renderer] Texture {tex.source} loaded: {pimg.width}x{pimg.height}")

#     def _parse_blendshapes(self):
#         vrm_ext = self.gltf.extensions.get("VRM", {}) if self.gltf.extensions else {}
#         self.blendshape_groups = vrm_ext.get("blendShapeMaster", {}).get("blendShapeGroups", [])

#     def update_blendshapes(self, weights: Dict[str, float]):
#         mapping = {"eyeBlinkLeft":"blink_l", "eyeBlinkRight":"blink_r", "jawOpen":"a"}
#         self.active_blendshapes = {mapping[k]:v for k,v in weights.items() if k in mapping}

#     def update_pose(self, bones: Dict[str, Any]):
#         for n, q in bones.items():
#             if n in self.bone_node_map:
#                 self.nodes[self.bone_node_map[n]].rotation = glm.quat(q[3], q[0], q[1], q[2])

#     def _compute_matrices(self):
#         def up(idx, pmat):
#             node = self.nodes[idx]
#             m = pmat * glm.translate(glm.mat4(1.0), node.translation) * glm.mat4_cast(node.rotation) * glm.scale(glm.mat4(1.0), node.scale)
#             node.global_matrix = m
#             node.skin_matrix = m * node.inverse_bind_matrix
#             for c in node.children: up(c, m)
#         for i, node in enumerate(self.nodes):
#             if node.parent is None: up(i, glm.mat4(1.0))

#     def _apply_blendshapes(self):
#         for mp in self.mesh_primitives:
#             if not mp.has_morphs: continue
#             mp.current_positions[:] = mp.base_positions
#             mod = False
#             for g in self.blendshape_groups:
#                 w = self.active_blendshapes.get(g.get("presetName", "").lower(), 0.0)
#                 if w > 0:
#                     for b in g.get("binds", []):
#                         if b["mesh"] == mp.mesh_index:
#                             mp.current_positions += mp.morph_targets[b["index"]] * (b["weight"]/100.0 * w)
#                             mod = True
#             if mod:
#                 glBindBuffer(GL_ARRAY_BUFFER, mp.vbos['POSITION'])
#                 glBufferSubData(GL_ARRAY_BUFFER, 0, mp.current_positions.nbytes, mp.current_positions)

#     def render(self):
#         if glfw.window_should_close(self.window):
#             self.should_close = True
#             return np.zeros((480, 640, 3), dtype=np.uint8)
#         glfw.make_context_current(self.window)
#         glClearColor(0.2, 0.3, 0.4, 1.0)
#         glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
#         if not self.gltf:
#             glfw.swap_buffers(self.window)
#             glfw.poll_events()
#             return np.zeros((480, 640, 3), dtype=np.uint8)
#         self._apply_blendshapes()
#         self._compute_matrices()
#         self.shader.use()
#         self.shader.set_mat4("view", self.view)
#         self.shader.set_mat4("projection", self.projection)
#         self.shader.set_mat4("model", self.model)
#         mats = np.zeros((128, 16), dtype=np.float32)
#         for i, node in enumerate(self.nodes):
#             if i < 128: mats[i] = np.array(node.skin_matrix).flatten()
#         loc = glGetUniformLocation(self.shader.program, "boneMatrices")
#         if loc != -1: glUniformMatrix4fv(loc, 128, GL_FALSE, mats)
#         for mp in self.mesh_primitives:
#             glBindVertexArray(mp.vao)
#             mat = self.gltf.materials[mp.material_index] if mp.material_index >= 0 else None
#             col = mat.pbrMetallicRoughness.baseColorFactor if mat and mat.pbrMetallicRoughness.baseColorFactor else [1,1,1,1]
#             self.shader.set_vec4("baseColorFactor", col)
#             if mat and mat.pbrMetallicRoughness.baseColorTexture:
#                 glActiveTexture(GL_TEXTURE0)
#                 glBindTexture(GL_TEXTURE_2D, self.textures[mat.pbrMetallicRoughness.baseColorTexture.index])
#                 self.shader.set_int("baseColorTexture", 0)
#                 self.shader.set_int("hasTexture", 1)
#             else: self.shader.set_int("hasTexture", 0)
#             glDrawElements(GL_TRIANGLES, mp.indices_count, GL_UNSIGNED_INT, None)
#         glfw.swap_buffers(self.window)
#         glfw.poll_events()
#         return np.zeros((480, 640, 3), dtype=np.uint8)

#     def resize(self, w, h):
#         glViewport(0, 0, w, h)
#         self.projection = glm.perspective(glm.radians(30.0), w/h, 0.05, 50.0)

#     def __del__(self):
#         if self.window: glfw.terminate()

import os
import io
import glfw
import glm
import math
import numpy as np
from OpenGL.GL import *
from pygltflib import GLTF2
from PIL import Image
from typing import Dict, Any, List, Optional
from .shader_utils import Shader

VRM_BONE_MAP = {
    "hips": "hips", "spine": "spine", "chest": "chest",
    "neck": "neck", "head": "head",
    "leftUpperArm": "leftUpperArm", "leftLowerArm": "leftLowerArm",
    "rightUpperArm": "rightUpperArm", "rightLowerArm": "rightLowerArm"
}

VERTEX_SHADER = """
#version 330 core
layout (location = 0) in vec3 position;
layout (location = 1) in vec3 normal;
layout (location = 2) in vec2 texcoord;
layout (location = 3) in ivec4 joints;
layout (location = 4) in vec4 weights;

uniform mat4 boneMatrices[128];
uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

out vec3 FragPos;
out vec3 Normal;
out vec2 TexCoord;

void main() {
    float tw = weights.x + weights.y + weights.z + weights.w;
    mat4 skin = (tw > 0.001)
        ? (weights.x * boneMatrices[joints.x] +
           weights.y * boneMatrices[joints.y] +
           weights.z * boneMatrices[joints.z] +
           weights.w * boneMatrices[joints.w])
        : mat4(1.0);
    vec4 wp     = model * skin * vec4(position, 1.0);
    FragPos     = wp.xyz;
    Normal      = normalize(mat3(transpose(inverse(model * skin))) * normal);
    TexCoord    = texcoord;
    gl_Position = projection * view * wp;
}
"""

FRAGMENT_SHADER = """
#version 330 core
out vec4 FragColor;
in vec3 FragPos;
in vec3 Normal;
in vec2 TexCoord;
uniform vec4      baseColorFactor;
uniform sampler2D baseColorTexture;
uniform int       hasTexture;

void main() {
    vec3 L    = normalize(vec3(0.5, 1.0, 0.8));
    float d   = max(dot(normalize(Normal), L), 0.0);
    vec3 lit  = vec3(0.35) + d * vec3(0.65);
    vec4 tex  = (hasTexture == 1) ? texture(baseColorTexture, TexCoord) : vec4(1.0);
    vec4 fc   = tex * baseColorFactor;
    if (fc.a < 0.05) discard;
    FragColor = vec4(lit * fc.rgb, fc.a);
}
"""

def _glm_mat4_to_numpy(m) -> np.ndarray:
    """Convert glm.mat4 to a column-major float32 numpy array (what OpenGL expects)."""
    return np.array([m[col][row] for col in range(4) for row in range(4)], dtype=np.float32)

def _check_gl_error(tag=""):
    err = glGetError()
    if err != GL_NO_ERROR:
        print(f"[GL ERROR] {tag}: {hex(err)}")
        return False
    return True


class Node:
    def __init__(self, index, name=""):
        self.index = index
        self.name  = name
        self.parent: Optional[int] = None
        self.children: List[int] = []
        self.translation = glm.vec3(0.0)
        self.rotation    = glm.quat(1.0, 0.0, 0.0, 0.0)
        self.scale       = glm.vec3(1.0)
        self.inverse_bind_matrix = glm.mat4(1.0)
        self.global_matrix = glm.mat4(1.0)
        self.skin_matrix   = glm.mat4(1.0)

class MeshPrimitive:
    def __init__(self, mesh_index, primitive_index):
        self.mesh_index      = mesh_index
        self.primitive_index = primitive_index
        self.vao = 0
        self.vbos: Dict[str, int] = {}
        self.indices_count = 0
        self.material_index = -1
        self.morph_targets: List[np.ndarray] = []
        self.base_positions    = None
        self.current_positions = None
        self.has_morphs = False


class VRMRenderer:
    def __init__(self):
        self.window   = None
        self.shader   = None
        self.gltf: Optional[GLTF2] = None
        self.nodes: List[Node] = []
        self.mesh_primitives: List[MeshPrimitive] = []
        self.textures: List[int] = []
        self.bone_node_map: Dict[str, int] = {}
        self.blendshape_groups: List[Dict] = []
        self.active_blendshapes: Dict[str, float] = {}
        self.should_close = False
        self._binary_blob_cache: Optional[bytes] = None
        self._frame = 0

        self.model      = glm.mat4(1.0)
        self.view       = glm.mat4(1.0)
        self.projection = glm.mat4(1.0)

        self._init_glfw()
        self.shader = Shader(VERTEX_SHADER, FRAGMENT_SHADER)
        self._set_default_camera()

    # ---------------------------------------------------------------- GLFW
    def _init_glfw(self):
        if not glfw.init():
            raise RuntimeError("GLFW init failed")
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE,        glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
        self.window = glfw.create_window(640, 480, "VRM Renderer", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Window creation failed")
        print("[Renderer] GLFW window created (640x480)")
        glfw.make_context_current(self.window)
        self._root_vao = glGenVertexArrays(1)
        glBindVertexArray(self._root_vao)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        print(f"[Renderer] OpenGL {glGetString(GL_VERSION).decode()}")

    def _set_default_camera(self):
        self.projection = glm.perspective(glm.radians(30.0), 640/480, 0.01, 500.0)
        self.view = glm.lookAt(glm.vec3(0, 1.0, 4.0),
                               glm.vec3(0, 1.0, 0.0),
                               glm.vec3(0, 1.0, 0.0))

    # --------------------------------------------------------------- load
    def load_vrm(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".fbx":
            print("[Renderer] FBX not supported — convert to .vrm/.glb in Blender"); return
        if ext not in (".vrm", ".glb", ".gltf"):
            print(f"[Renderer] Unsupported: {ext}"); return

        print(f"[Renderer] Loading: {path}")
        self.vrm_dir = os.path.dirname(os.path.abspath(path))
        self._binary_blob_cache = None
        self.nodes, self.mesh_primitives, self.textures = [], [], []
        self.bone_node_map, self.blendshape_groups      = {}, []
        self.gltf = None

        try:
            self.gltf = GLTF2().load_binary(path) if ext in (".vrm", ".glb") else GLTF2().load(path)
        except Exception as e:
            print(f"[Renderer] Load error: {e}"); return

        try:
            self._binary_blob_cache = self.gltf.binary_blob()
            print(f"[Renderer] Binary blob: {len(self._binary_blob_cache)} bytes")
        except Exception as e:
            print(f"[Renderer] No binary blob: {e}")

        self._parse_nodes()
        self._parse_skeleton()
        bbox_min, bbox_max = self._parse_meshes()
        if bbox_min is not None:
            self._fit_camera_to_bbox(bbox_min, bbox_max)
        self._parse_textures()
        self._parse_blendshapes()
        _check_gl_error("after load")
        print("[Renderer] Load complete ✓")

    # ----------------------------------------------------------- camera fit
    def _fit_camera_to_bbox(self, bbox_min: np.ndarray, bbox_max: np.ndarray):
        centre = (bbox_min + bbox_max) * 0.5
        size   = bbox_max - bbox_min
        height = float(size[1])
        if height < 1e-9:
            print("[Renderer] Degenerate bbox — skipping auto-fit"); return

        target_h     = 1.6
        scale_factor = target_h / height
        print(f"[Renderer] Auto-fit: height={height:.6f}  scale={scale_factor:.4f}")

        # Build model matrix so feet land at y=0, centred in XZ
        s  = scale_factor
        cx = float(centre[0]) * s
        cz = float(centre[2]) * s
        bottom_y = float(bbox_min[1]) * s

        self.model = (
            glm.translate(glm.mat4(1.0), glm.vec3(-cx, -bottom_y, -cz)) *
            glm.scale(glm.mat4(1.0), glm.vec3(s))
        )

        # Camera distance to frame full height with 30° vFOV
        dist  = (target_h / 2.0) / math.tan(math.radians(15.0)) + 0.3
        mid_y = target_h * 0.5

        self.view = glm.lookAt(
            glm.vec3(0.0, mid_y, dist),
            glm.vec3(0.0, mid_y, 0.0),
            glm.vec3(0.0, 1.0,   0.0)
        )
        self.projection = glm.perspective(glm.radians(30.0), 640/480, 0.01, dist * 20)
        print(f"[Renderer] Camera: dist={dist:.2f}  eye_y={mid_y:.2f}")

    # --------------------------------------------------------- buffer helpers
    def _get_buffer_bytes(self, bv_idx: int) -> bytes:
        bv  = self.gltf.bufferViews[bv_idx]
        buf = self.gltf.buffers[bv.buffer]
        off = bv.byteOffset or 0
        ln  = bv.byteLength
        if buf.uri is None:
            if not self._binary_blob_cache: return b""
            return self._binary_blob_cache[off: off + ln]
        if buf.uri.startswith("data:"):
            import base64
            return base64.b64decode(buf.uri.split(",", 1)[1])[off: off + ln]
        with open(os.path.join(self.vrm_dir, buf.uri), "rb") as f:
            f.seek(off); return f.read(ln)

    def _get_buffer_data(self, acc_idx: int) -> np.ndarray:
        acc   = self.gltf.accessors[acc_idx]
        dtype = {5120:np.int8, 5121:np.uint8, 5122:np.int16,
                 5123:np.uint16, 5125:np.uint32, 5126:np.float32}[acc.componentType]
        comps = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}[acc.type]
        raw   = self._get_buffer_bytes(acc.bufferView)
        off   = acc.byteOffset or 0
        bv    = self.gltf.bufferViews[acc.bufferView]
        elem  = np.dtype(dtype).itemsize * comps
        stride = bv.byteStride or elem
        arr   = np.zeros((acc.count, comps), dtype=dtype)
        for i in range(acc.count):
            s = off + i * stride
            chunk = raw[s: s + elem]
            if len(chunk) == elem:
                arr[i] = np.frombuffer(chunk, dtype=dtype)
        return arr

    # ------------------------------------------------------------ parse
    def _parse_nodes(self):
        self.nodes = []
        for i, gn in enumerate(self.gltf.nodes):
            n = Node(i, gn.name or "")
            if gn.translation: n.translation = glm.vec3(*gn.translation)
            if gn.rotation:    n.rotation    = glm.quat(gn.rotation[3], *gn.rotation[:3])
            if gn.scale:       n.scale       = glm.vec3(*gn.scale)
            if gn.children:    n.children    = list(gn.children)
            self.nodes.append(n)
        for i, n in enumerate(self.nodes):
            for c in n.children: self.nodes[c].parent = i
        print(f"[Renderer] {len(self.nodes)} nodes parsed")

    def _parse_skeleton(self):
        vrm_ext  = (self.gltf.extensions or {}).get("VRM", {})
        humanoid = vrm_ext.get("humanoid", {})
        vrm_map  = {b["bone"]: b["node"] for b in humanoid.get("humanBones", [])}
        for vn, inn in VRM_BONE_MAP.items():
            if inn in vrm_map: self.bone_node_map[vn] = vrm_map[inn]
        print(f"[Renderer] {len(self.bone_node_map)} bones mapped")
        if self.gltf.skins:
            skin = self.gltf.skins[0]
            print(f"[Renderer] Skin joints: {len(skin.joints)}")
            if skin.inverseBindMatrices is not None:
                ibm = self._get_buffer_data(skin.inverseBindMatrices)
                for i, ji in enumerate(skin.joints):
                    if ji < len(self.nodes):
                        vals = ibm[i].astype(np.float32).flatten().tolist()
                        self.nodes[ji].inverse_bind_matrix = glm.mat4(*vals)

    def _parse_meshes(self):
        self.mesh_primitives = []
        g_min = np.full(3,  1e18, dtype=np.float32)
        g_max = np.full(3, -1e18, dtype=np.float32)
        total_verts = 0

        for midx, gm in enumerate(self.gltf.meshes):
            for pidx, prim in enumerate(gm.primitives):
                mp = MeshPrimitive(midx, pidx)
                mp.material_index = prim.material if prim.material is not None else -1

                mp.vao = glGenVertexArrays(1)
                glBindVertexArray(mp.vao)
                _check_gl_error(f"bind VAO {midx}.{pidx}")

                at = prim.attributes

                # ---- position (loc 0)
                if at.POSITION is not None:
                    pos = self._get_buffer_data(at.POSITION).astype(np.float32)
                    total_verts += len(pos)
                    g_min = np.minimum(g_min, pos.min(0))
                    g_max = np.maximum(g_max, pos.max(0))
                    mp.base_positions    = pos.copy()
                    mp.current_positions = pos.copy()
                    vbo = glGenBuffers(1)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo)
                    glBufferData(GL_ARRAY_BUFFER, pos.nbytes, pos, GL_DYNAMIC_DRAW)
                    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
                    glEnableVertexAttribArray(0)
                    mp.vbos['POSITION'] = vbo
                    _check_gl_error("pos upload")
                else:
                    print(f"[Renderer] WARNING: primitive {midx}.{pidx} has no POSITION")

                # ---- normal (loc 1)
                if at.NORMAL is not None:
                    norm = self._get_buffer_data(at.NORMAL).astype(np.float32)
                    vbo  = glGenBuffers(1)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo)
                    glBufferData(GL_ARRAY_BUFFER, norm.nbytes, norm, GL_STATIC_DRAW)
                    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
                    glEnableVertexAttribArray(1)
                    mp.vbos['NORMAL'] = vbo
                else:
                    print(f"[Renderer] WARNING: primitive {midx}.{pidx} has no NORMAL — flat shading will be wrong")

                # ---- texcoord (loc 2)
                if at.TEXCOORD_0 is not None:
                    uv  = self._get_buffer_data(at.TEXCOORD_0).astype(np.float32)
                    vbo = glGenBuffers(1)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo)
                    glBufferData(GL_ARRAY_BUFFER, uv.nbytes, uv, GL_STATIC_DRAW)
                    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 0, None)
                    glEnableVertexAttribArray(2)
                    mp.vbos['TEXCOORD_0'] = vbo

                # ---- joints (loc 3)
                if at.JOINTS_0 is not None:
                    jdata = self._get_buffer_data(at.JOINTS_0).astype(np.int32)
                    vbo   = glGenBuffers(1)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo)
                    glBufferData(GL_ARRAY_BUFFER, jdata.nbytes, jdata, GL_STATIC_DRAW)
                    glVertexAttribIPointer(3, 4, GL_INT, 0, None)
                    glEnableVertexAttribArray(3)
                    mp.vbos['JOINTS_0'] = vbo
                else:
                    print(f"[Renderer] No JOINTS_0 — mesh will use identity skin")

                # ---- weights (loc 4)
                if at.WEIGHTS_0 is not None:
                    wdata = self._get_buffer_data(at.WEIGHTS_0).astype(np.float32)
                    vbo   = glGenBuffers(1)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo)
                    glBufferData(GL_ARRAY_BUFFER, wdata.nbytes, wdata, GL_STATIC_DRAW)
                    glVertexAttribPointer(4, 4, GL_FLOAT, GL_FALSE, 0, None)
                    glEnableVertexAttribArray(4)
                    mp.vbos['WEIGHTS_0'] = vbo

                # ---- indices
                if prim.indices is not None:
                    idx = self._get_buffer_data(prim.indices).astype(np.uint32).flatten()
                    mp.indices_count = len(idx)
                    ebo = glGenBuffers(1)
                    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
                    glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx, GL_STATIC_DRAW)
                    print(f"[Renderer]   prim {midx}.{pidx}: {len(idx)} indices  mat={mp.material_index}")
                else:
                    print(f"[Renderer] WARNING: no indices for prim {midx}.{pidx}")

                # ---- morph targets
                if prim.targets:
                    mp.has_morphs = True
                    for t in prim.targets:
                        pk = t.get("POSITION") if isinstance(t, dict) else getattr(t, "POSITION", None)
                        if pk is not None:
                            mp.morph_targets.append(self._get_buffer_data(pk).astype(np.float32))

                self.mesh_primitives.append(mp)
                glBindVertexArray(0)

        print(f"[Renderer] {len(self.mesh_primitives)} primitives, {total_verts} verts")
        print(f"[Renderer] BBox min={g_min}  max={g_max}  size={g_max - g_min}")
        return (g_min, g_max) if total_verts > 0 else (None, None)

    def _parse_textures(self):
        self.textures = []
        if not self.gltf.textures:
            print("[Renderer] No textures in file"); return
        for ti, tex in enumerate(self.gltf.textures):
            if tex.source is None:
                self.textures.append(0); continue
            img = self.gltf.images[tex.source]
            try:
                if img.uri and img.uri.startswith("data:"):
                    import base64
                    data = base64.b64decode(img.uri.split(",",1)[1])
                elif img.bufferView is not None:
                    data = self._get_buffer_bytes(img.bufferView)
                elif img.uri:
                    with open(os.path.join(self.vrm_dir, img.uri),"rb") as f: data = f.read()
                else:
                    self.textures.append(0); continue

                pimg  = Image.open(io.BytesIO(data)).convert("RGBA")
                pdata = np.array(pimg, dtype=np.uint8)
                tid   = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, tid)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, pimg.width, pimg.height,
                             0, GL_RGBA, GL_UNSIGNED_BYTE, pdata)
                glGenerateMipmap(GL_TEXTURE_2D)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                self.textures.append(tid)
                print(f"[Renderer] Tex[{ti}]: {pimg.width}x{pimg.height}  glId={tid}")
            except Exception as e:
                print(f"[Renderer] Texture {ti} error: {e}")
                self.textures.append(0)

    def _parse_blendshapes(self):
        vrm_ext = (self.gltf.extensions or {}).get("VRM", {})
        self.blendshape_groups = vrm_ext.get("blendShapeMaster", {}).get("blendShapeGroups", [])
        print(f"[Renderer] {len(self.blendshape_groups)} blendshape groups")

    # ---------------------------------------------------------- runtime
    def update_blendshapes(self, weights: Dict[str, float]):
        m = {"eyeBlinkLeft":"blink_l","eyeBlinkRight":"blink_r","jawOpen":"a"}
        self.active_blendshapes = {m[k]:v for k,v in weights.items() if k in m}

    def update_pose(self, bones: Dict[str, Any]):
        for name, q in bones.items():
            if name in self.bone_node_map:
                ni = self.bone_node_map[name]
                self.nodes[ni].rotation = glm.quat(q[3], q[0], q[1], q[2])

    def get_rest_poses(self) -> Dict[str, List[float]]:
        rest_poses = {}
        for bone_name, node_idx in self.bone_node_map.items():
            if node_idx < len(self.nodes):
                node = self.nodes[node_idx]
                # glm.quat is (w, x, y, z), we return [x, y, z, w]
                q = node.rotation
                rest_poses[bone_name] = [q.x, q.y, q.z, q.w]
        return rest_poses

    def _compute_matrices(self):
        def up(idx, pm):
            n  = self.nodes[idx]
            lm = (glm.translate(glm.mat4(1.0), n.translation) *
                  glm.mat4_cast(n.rotation) *
                  glm.scale(glm.mat4(1.0), n.scale))
            n.global_matrix = pm * lm
            n.skin_matrix   = n.global_matrix * n.inverse_bind_matrix
            for c in n.children: up(c, n.global_matrix)
        for i, n in enumerate(self.nodes):
            if n.parent is None: up(i, glm.mat4(1.0))

    def _apply_blendshapes(self):
        for mp in self.mesh_primitives:
            if not mp.has_morphs: continue
            mp.current_positions[:] = mp.base_positions
            mod = False
            for g in self.blendshape_groups:
                w = self.active_blendshapes.get(g.get("presetName","").lower(), 0.0)
                if w > 0:
                    for b in g.get("binds", []):
                        ti = b.get("index", -1)
                        if b.get("mesh") == mp.mesh_index and 0 <= ti < len(mp.morph_targets):
                            mp.current_positions += mp.morph_targets[ti] * (b["weight"]/100.0*w)
                            mod = True
            if mod:
                glBindBuffer(GL_ARRAY_BUFFER, mp.vbos['POSITION'])
                glBufferSubData(GL_ARRAY_BUFFER, 0,
                                mp.current_positions.nbytes, mp.current_positions)

    def _upload_uniform_mat4(self, loc, mat):
        """Upload a glm.mat4 correctly as column-major to OpenGL."""
        data = _glm_mat4_to_numpy(mat)
        glUniformMatrix4fv(loc, 1, GL_FALSE, data)

    def render(self) -> np.ndarray:
        self._frame += 1
        debug = (self._frame == 1)  # only log on first frame after load

        if glfw.window_should_close(self.window):
            self.should_close = True
            return np.zeros((480,640,3), dtype=np.uint8)

        glfw.make_context_current(self.window)
        glClearColor(0.18, 0.22, 0.28, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        if not self.gltf or not self.mesh_primitives:
            glfw.swap_buffers(self.window)
            glfw.poll_events()
            return np.zeros((480,640,3), dtype=np.uint8)

        self._apply_blendshapes()
        self._compute_matrices()

        self.shader.use()
        _check_gl_error("use shader")

        # Upload matrices correctly (column-major)
        loc_v  = glGetUniformLocation(self.shader.program, "view")
        loc_p  = glGetUniformLocation(self.shader.program, "projection")
        loc_m  = glGetUniformLocation(self.shader.program, "model")
        loc_bm = glGetUniformLocation(self.shader.program, "boneMatrices")

        if debug:
            print(f"[Renderer] Uniform locs: view={loc_v} proj={loc_p} model={loc_m} bones={loc_bm}")

        if loc_v  != -1: self._upload_uniform_mat4(loc_v,  self.view)
        if loc_p  != -1: self._upload_uniform_mat4(loc_p,  self.projection)
        if loc_m  != -1: self._upload_uniform_mat4(loc_m,  self.model)

        # Identity bone matrices (column-major eye(4) repeated 128x)
        eye_flat = np.eye(4, dtype=np.float32).flatten()   # already col-major for identity
        bone_data = np.tile(eye_flat, 128).reshape(128, 16).astype(np.float32)
        for i, node in enumerate(self.nodes):
            if i >= 128: break
            bone_data[i] = _glm_mat4_to_numpy(node.skin_matrix)

        if loc_bm != -1:
            glUniformMatrix4fv(loc_bm, 128, GL_FALSE, bone_data)
        _check_gl_error("upload matrices")

        drawn = 0
        for mp in self.mesh_primitives:
            if mp.indices_count == 0:
                if debug: print(f"[Renderer] Skip prim — no indices")
                continue

            glBindVertexArray(mp.vao)
            _check_gl_error(f"bind VAO {mp.mesh_index}")

            base_color = [1.0, 1.0, 1.0, 1.0]
            has_tex    = 0

            if (mp.material_index >= 0
                    and self.gltf.materials
                    and mp.material_index < len(self.gltf.materials)):
                mat = self.gltf.materials[mp.material_index]
                pbr = mat.pbrMetallicRoughness
                if pbr:
                    if pbr.baseColorFactor:
                        base_color = list(pbr.baseColorFactor)
                    if pbr.baseColorTexture is not None:
                        ti = pbr.baseColorTexture.index
                        if 0 <= ti < len(self.textures) and self.textures[ti]:
                            glActiveTexture(GL_TEXTURE0)
                            glBindTexture(GL_TEXTURE_2D, self.textures[ti])
                            loc_tex = glGetUniformLocation(self.shader.program, "baseColorTexture")
                            if loc_tex != -1: glUniform1i(loc_tex, 0)
                            has_tex = 1

            loc_col = glGetUniformLocation(self.shader.program, "baseColorFactor")
            loc_ht  = glGetUniformLocation(self.shader.program, "hasTexture")
            if loc_col != -1: glUniform4fv(loc_col, 1, np.array(base_color, dtype=np.float32))
            if loc_ht  != -1: glUniform1i(loc_ht, has_tex)

            if debug:
                print(f"[Renderer]   Drawing prim {mp.mesh_index}.{mp.primitive_index}: "
                      f"{mp.indices_count} indices  color={base_color}  tex={has_tex}")

            glDrawElements(GL_TRIANGLES, mp.indices_count, GL_UNSIGNED_INT, None)
            err = glGetError()
            if err != GL_NO_ERROR:
                print(f"[Renderer] glDrawElements error: {hex(err)}")
            else:
                drawn += 1

        if debug:
            print(f"[Renderer] Drew {drawn}/{len(self.mesh_primitives)} primitives")

        glfw.swap_buffers(self.window)
        glfw.poll_events()
        return np.zeros((480,640,3), dtype=np.uint8)

    def resize(self, w: int, h: int):
        glViewport(0, 0, w, h)
        self.projection = glm.perspective(glm.radians(30.0), w/h, 0.01, 500.0)

    def __del__(self):
        if self.window:
            glfw.terminate()