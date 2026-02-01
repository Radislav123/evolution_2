from typing import Any

from pyglet.graphics.shader import ComputeShaderProgram, ShaderException, ShaderProgram
from pyglet.math import Vec3

from core.service.logger import Logger
from core.service.object import ProjectMixin
from core.service.settings import Settings
from core.service.singleton import Singleton


settings = Settings()
logger = Logger(__name__)

ShaderReplacements = dict[str, Any]


class UniformSetError(Exception):
    pass


class Replacements(Singleton, ProjectMixin):
    def __init__(self) -> None:
        super().__init__()

        self.WORLD_SEED = str(self.settings.WORLD_SEED)

        self.WORLD_SHAPE = self.ivec3(self.settings.WORLD_SHAPE)
        self.BLOCK_SHAPE = self.ivec3(self.settings.BLOCK_SHAPE)
        self.CELL_SHAPE = self.ivec3(self.settings.CELL_SHAPE)
        self.WORLD_UNIT_SHAPE = self.ivec3(self.settings.WORLD_UNIT_SHAPE)

        self.CELL_GROUP_SHAPE = self.ivec3(self.settings.CELL_GROUP_SHAPE)

        self.all = {f"{key.lower()}_placeholder": value for key, value in self.__dict__.items()}

    @staticmethod
    def vector(vector_type: str, vector: Vec3) -> str:
        return f"{vector_type}{tuple(vector)}"

    @classmethod
    def vec3(cls, vector: Vec3) -> str:
        return cls.vector("vec3", vector)

    @classmethod
    def ivec3(cls, vector: Vec3) -> str:
        return cls.vector("ivec3", vector)


REPLACEMENTS = Replacements()


class Includes(Singleton, ProjectMixin):
    def __init__(self) -> None:
        super().__init__()

        self.COLOR_FUNCTION = f"{self.settings.PROJECTIONAL_SHADERS}/functions/get_cell_color/{"default" if not self.settings.TEST_COLOR_CUBE else "test_color_cube"}.glsl"

        self.PHYSICAL_CONSTANTS = f"{self.settings.SHADERS}/constants/physical.glsl"
        self.PACKING_CONSTANTS = f"{self.settings.SHADERS}/constants/packing.glsl"
        self.COMMON_CONSTANTS = f"{self.settings.SHADERS}/constants/common.glsl"

        self.CELL_PACKING = f"{self.settings.PHYSICAL_SHADERS}/components/cell.glsl"
        self.UNIT_PACKING = f"{self.settings.PHYSICAL_SHADERS}/components/unit.glsl"
        self.SUBSTANCE_PACKING = f"{self.settings.PHYSICAL_SHADERS}/components/substance.glsl"

        for key, path in self.__dict__.items():
            with open(path, "r", encoding = settings.SHADER_ENCODING) as include_file:
                setattr(self, key, include_file.read())

        self.all = {f"#include {key.lower()}": value for key, value in self.__dict__.items()}


INCLUDES = Includes()


def load_shader(shader_path: str) -> str:
    shader_source = ""
    with open(shader_path, "r", encoding = settings.SHADER_ENCODING) as shader_file:
        shader_source = shader_file.read()

    for placeholder, value in INCLUDES.all.items():
        shader_source = shader_source.replace(placeholder, value)

    for placeholder, value in REPLACEMENTS.all.items():
        shader_source = shader_source.replace(placeholder, str(value))

    return shader_source


def write_uniforms(program: ShaderProgram | ComputeShaderProgram, uniforms: dict[str, tuple[Any, bool, bool]]) -> None:
    for key, (value, raise_error, show_warning) in uniforms.items():
        try:
            program[key] = value
        except ShaderException as error:
            if raise_error:
                raise UniformSetError(f"{key} was not set") from error
            # Предупреждение можно не показывать, если это, к примеру, переменная из #include,
            # а #include подключается по условию (как get_unit_color для fragment.glsl)
            if show_warning:
                logger.warning(str(error))
