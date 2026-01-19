from itertools import count, takewhile
from typing import Any, Iterator, Type, TypeVar

from arcade.gl import ComputeShader, Program

from core.service.logger import Logger
from core.service.settings import Settings


settings = Settings()
logger = Logger(__name__)

T = TypeVar("T")
ShaderReplacements = dict[str, Any]


def float_range(start: float, stop: float, step: float) -> Iterator[float]:
    return takewhile(lambda x: x < stop, count(start, step))


def get_subclasses(cls) -> list[Type[T]]:
    """Возвращает все дочерние классы рекурсивно."""

    subclasses = cls.__subclasses__()
    child_subclasses = []
    for child in subclasses:
        child_subclasses.extend(get_subclasses(child))
    subclasses.extend(child_subclasses)
    return subclasses


# performance: Добавить кэширование файлов
def load_shader(
        shader_path: str,
        includes: dict[str, tuple[str, ShaderReplacements]] = None,
        replacements: ShaderReplacements = None
) -> str:
    if includes is None:
        includes = {}
    if replacements is None:
        replacements = {}

    with open(shader_path, "r", encoding = settings.SHADER_ENCODING) as shader_file:
        code_source = shader_file.read()

    for placeholder, (include, include_replacements) in includes.items():
        with open(include, "r", encoding = settings.SHADER_ENCODING) as include_file:
            include_source = include_file.read()
            for include_placeholder, value in include_replacements:
                include_source = include_source.replace(include_placeholder, value)
            code_source = code_source.replace(f"#include {placeholder}", include_source)

    for placeholder, value in replacements.items():
        code_source = code_source.replace(placeholder, str(value))

    return code_source


def write_uniforms(program: Program | ComputeShader, uniforms: dict[str, tuple[Any, bool, bool]]) -> None:
    for key, (value, raise_error, show_warning) in uniforms.items():
        try:
            program[key] = value
        except KeyError as error:
            program.set_uniform_safe(key, value)
            if raise_error:
                raise error
            # Предупреждение можно не показывать, если это, к примеру, переменная из #include,
            # а #include подключается по условию (как get_voxel_color для fragment.glsl)
            if show_warning:
                logger.warning(str(error))
