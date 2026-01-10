from array import array

from arcade import ArcadeContext
from arcade.gl import BufferDescription, Geometry
from arcade.types import Point3

from core.service.object import ProjectionObject
from core.service.singleton import Singleton


# Оставлен, так как жалко удалять
class Voxel(ProjectionObject, Singleton):
    # Координаты вершин
    vertices = (
        # (x, y, z)
        (0, 0, 0),
        (0, 1, 0),
        (1, 1, 0),
        (1, 0, 0),
        (0, 0, 1),
        (0, 1, 1),
        (1, 1, 1),
        (1, 0, 1)
    )
    # Индексы точек граней
    face_vertex_indexes = (
        # Нижняя
        (0, 1, 2, 3),
        # Передняя
        (3, 7, 4, 0),
        # Правая
        (2, 6, 7, 3),
        # Задняя
        (1, 5, 6, 2),
        # Левая
        (0, 4, 5, 1),
        # Верхняя
        (7, 6, 5, 4)
    )
    # Нормали граней
    face_normals = (
        (0, 0, -1),
        (0, -1, 0),
        (1, 0, 0),
        (0, 1, 0),
        (-1, 0, 0),
        (0, 0, 1)
    )
    # Порядок обхода граней
    face_order = (0, 1, 2, 3, 4, 5)
    # Разбиение четырехугольника на треугольники
    triangles = (
        0, 1, 2,
        0, 2, 3
    )

    @classmethod
    def generate_geometry(cls, ctx: ArcadeContext, size: Point3 = (1, 1, 1), center: Point3 = (0, 0, 0)) -> Geometry:
        offset = tuple(component / 2 for component in size)

        positions = array(
            'f',
            (center[component_index] + vertex[component_index] - offset[component_index]
             for vertex in
             (cls.vertices[cls.face_vertex_indexes[face_index][face_vertex_index]]
              for face_index in cls.face_order
              for face_vertex_index in cls.triangles)
             for component_index in range(3)
             )
        )

        normals = array(
            'f',
            (cls.face_normals[face_index][component_index]
             for face_index in cls.face_order
             for _ in cls.triangles
             for component_index in range(3))
        )

        return ctx.geometry(
            [
                BufferDescription(ctx.buffer(data = positions), "3f", ["in_position"]),
                BufferDescription(ctx.buffer(data = normals), "3f", ["in_normal"])
            ]
        )
