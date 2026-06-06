import numpy as np
from OpenGL.GL import *
from OpenGL.GL import shaders


class Shader:
    def __init__(self, vertex_source: str, fragment_source: str):
        try:
            vs = shaders.compileShader(vertex_source,   GL_VERTEX_SHADER)
            fs = shaders.compileShader(fragment_source, GL_FRAGMENT_SHADER)
        except shaders.ShaderCompilationError as e:
            print(f"[Shader] Compilation error:\n{e}")
            raise

        self.program = glCreateProgram()
        glAttachShader(self.program, vs)
        glAttachShader(self.program, fs)
        glLinkProgram(self.program)

        status = glGetProgramiv(self.program, GL_LINK_STATUS)
        if not status:
            log = glGetProgramInfoLog(self.program).decode()
            raise RuntimeError(f"[Shader] Link failed:\n{log}")

        glDetachShader(self.program, vs)
        glDetachShader(self.program, fs)
        glDeleteShader(vs)
        glDeleteShader(fs)
        print(f"[Shader] Program {self.program} linked OK")

    # NOTE: glValidateProgram is intentionally NOT called here.
    # On macOS Core Profile it validates against the *current* VAO/texture state,
    # which is empty at construction time and produces false failures.
    # Validation should only be done with a bound VAO + bound textures if needed for debugging.

    def use(self):
        glUseProgram(self.program)

    def _loc(self, name: str) -> int:
        return glGetUniformLocation(self.program, name)

    def set_mat4(self, name: str, mat):
        loc = self._loc(name)
        if loc == -1: return
        # Convert glm.mat4 to column-major float32 array
        data = np.array(
            [mat[col][row] for col in range(4) for row in range(4)],
            dtype=np.float32
        )
        glUniformMatrix4fv(loc, 1, GL_FALSE, data)

    def set_int(self, name: str, val: int):
        loc = self._loc(name)
        if loc != -1: glUniform1i(loc, int(val))

    def set_float(self, name: str, val: float):
        loc = self._loc(name)
        if loc != -1: glUniform1f(loc, float(val))

    def set_vec3(self, name: str, vec):
        loc = self._loc(name)
        if loc != -1: glUniform3fv(loc, 1, np.array(vec, dtype=np.float32))

    def set_vec4(self, name: str, vec):
        loc = self._loc(name)
        if loc != -1: glUniform4fv(loc, 1, np.array(vec, dtype=np.float32))