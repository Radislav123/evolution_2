from pyglet import gl
# noinspection PyProtectedMember
from pyglet.graphics.shader import _uniform_getters, _uniform_setters


def patch_gl() -> None:
    if gl.GL_UNSIGNED_INT_SAMPLER_BUFFER not in _uniform_setters:
        _uniform_setters[gl.GL_UNSIGNED_INT_SAMPLER_BUFFER] = _uniform_setters[gl.GL_SAMPLER_1D]
    else:
        raise ValueError(f"gl.GL_UNSIGNED_INT_SAMPLER_BUFFER already set")
    _uniform_getters[gl.GL_INT] = gl.glGetUniformiv
