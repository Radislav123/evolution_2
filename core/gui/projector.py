import math
from typing import TYPE_CHECKING

import arcade
from arcade.camera import CameraData, PerspectiveProjectionData, PerspectiveProjector
from arcade.gui import UIOnClickEvent
from pyglet.math import Mat4, Vec3, Vec4

from core.service.object import ProjectMixin


if TYPE_CHECKING:
    from simulator.window import ProjectWindow


class ProjectCameraData(CameraData, ProjectMixin):
    position: Vec3
    forward: Vec3
    right: Vec3
    up: Vec3

    def __init__(self, projector: "ProjectProjector") -> None:
        self.projector = projector
        self.rotation_radius = self.settings.CAMERA_ROTATION_RADIUS

        # Должен совпадать с World.center
        self.world_unit_center = Vec3(*self.settings.WORLD_UNIT_SHAPE) // 2
        # Отодвигаем камеру по z, чтобы видеть объекты в центре сцены
        self.centralized_position = self.world_unit_center + Vec3(0, 0, self.rotation_radius)
        self.centralized_forward = Vec3(0, 0, -1)
        self.centralized_up = Vec3(0, 1, 0)
        self.centralized_right = self.centralized_forward.cross(self.centralized_up).normalize()

        super().__init__(
            self.centralized_position,
            self.centralized_up,
            self.centralized_forward,
            self.settings.CAMERA_ZOOM
        )
        # Нормализация нужна, так как могут быть погрешности у чисел с ситуациями вида (1.00000000002, 0, 0)
        self.right = self.forward.cross(self.up).normalize()
        self.axis_sort_order: tuple[int, int, int] | None = None
        self.sort_direction: tuple[int, int, int] | None = None

    def centralize(self, _: UIOnClickEvent) -> None:
        self.position = self.centralized_position
        self.zoom = self.settings.CAMERA_ZOOM

        self.forward = self.centralized_forward
        self.right = self.centralized_right
        self.up = self.centralized_up

    # Перемещает камеру вправо/влево и вверх/вниз относительно направления взгляда и верха
    def pan(self, offset_x: float, offset_y: float) -> None:
        distance = abs(self.position.dot(self.forward))
        world_unit_per_pixel = ((2 * distance * self.projector.projection.fov_scale)
                                / self.projector.window.height / self.zoom)

        offset = (self.right * -offset_x + self.up * -offset_y) * world_unit_per_pixel
        self.position = self.position + offset

    # Перемещает камеру вперед/назад относительно направления взгляда
    def dolly(self, offset_z: float) -> None:
        self.position += self.forward * offset_z

    # Меняет зум и сдвигает картинку относительно курсора
    def change_zoom(self, offset: float) -> None:
        zoom_offset = offset * self.zoom * self.settings.CAMERA_ZOOM_SENSITIVITY

        self.zoom = max(
            min(self.zoom + zoom_offset, self.settings.CAMERA_MAX_ZOOM),
            self.settings.CAMERA_MIN_ZOOM
        )

    # Вращает камеру вокруг точки перед ней на расстоянии rotation_radius
    def rotate(self, offset_x: float, offset_y: float) -> None:
        # 1. Точка вращения и текущая позиция
        pivot = self.position + self.forward * self.rotation_radius

        # 2. Углы поворота
        dx = -offset_x / self.zoom * self.settings.CAMERA_ROTATION_SENSITIVITY
        dy = offset_y / self.zoom * self.settings.CAMERA_ROTATION_SENSITIVITY

        # 3. Вектор от pivot до камеры
        v4 = Vec4(*(self.position - pivot), 1)

        # 4. Матрицы вращения
        rotation_horizontal = Mat4.from_rotation(dx, self.up)
        rotation_vertical = Mat4.from_rotation(dy, self.right)

        # Умножаем через @ и сразу вырезаем первые 3 компонента (xyz)
        # Сначала горизонталь, потом вертикаль
        v4 = rotation_vertical @ (rotation_horizontal @ v4)
        v_final = Vec3(v4.x, v4.y, v4.z)

        # 5. Обновляем позицию
        self.position = pivot + v_final

        # 6. Направляем камеру обратно на pivot
        self.forward, self.up = arcade.camera.grips.look_at(self, pivot)
        self.right = self.forward.cross(self.up).normalize()


class ProjectPerspectiveProjectionData(PerspectiveProjectionData, ProjectMixin):
    def __init__(self, projector: "ProjectProjector") -> None:
        self.projector = projector
        super().__init__(
            self.projector.window.width / self.projector.window.height,
            self.settings.CAMERA_FOV,
            self.settings.CAMERA_NEAR,
            self.settings.CAMERA_FAR
        )

        self.fov_scale = math.tan(math.radians(self.fov) / 2)


class ProjectProjector(PerspectiveProjector, ProjectMixin):
    view: ProjectCameraData
    projection: ProjectPerspectiveProjectionData

    def __init__(self, window: "ProjectWindow") -> None:
        self.window = window
        camera_data = ProjectCameraData(self)
        projection = ProjectPerspectiveProjectionData(self)
        super().__init__(window = window, view = camera_data, projection = projection)

    def init(self) -> None:
        # noinspection PyTypeChecker
        self.view.centralize(UIOnClickEvent(self, None, None, None, None))
