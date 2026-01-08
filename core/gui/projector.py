import math
from typing import TYPE_CHECKING

import arcade
from arcade.camera import CameraData, PerspectiveProjector
from arcade.gui import UIOnClickEvent
from pyglet.math import Mat4, Vec3, Vec4

from core.service.object import ProjectMixin


if TYPE_CHECKING:
    from simulator.window import ProjectWindow


class ProjectCameraData(CameraData, ProjectMixin):
    def __init__(self, projector: "ProjectProjector") -> None:
        self.projector = projector

        self.rotation_radius = self.settings.CAMERA_ROTATION_RADIUS

        # Отодвигаем камеру по z, чтобы видеть объекты в центре сцены
        self.centralized_position = (0, 0, self.rotation_radius)
        # Должен совпадать с World.center
        self.world_center = (0, 0, 0)

        super().__init__(position = self.centralized_position, zoom = self.settings.CAMERA_ZOOM)
        self.axis_sort_order: tuple[int, int, int] | None = None
        self.forward_normal: tuple[int, int, int] | None = None
        self.sort_direction: tuple[int, int, int] | None = None

    def centralize(self, _: UIOnClickEvent) -> None:
        self.position = self.centralized_position
        self.zoom = self.settings.CAMERA_ZOOM

        self.forward, self.up = arcade.camera.grips.look_at(self, self.world_center)
        self.up = (0, 1, 0)
        # Для инициализации
        self.rotate(0, 0)

    # Перемещает камеру вправо/влево и вверх/вниз относительно направления взгляда и верха
    def pan(self, offset_x: float, offset_y: float) -> None:
        old_position = Vec3(*self.position)
        forward = Vec3(*self.forward)
        up = Vec3(*self.up)
        right = forward.cross(up)

        distance = abs(old_position.dot(forward))
        fov_radian = math.radians(self.projector.projection.fov)
        world_unit_per_pixel = (2 * distance * math.tan(fov_radian / 2)) / self.projector.window.height / self.zoom

        offset = (right * -offset_x + up * -offset_y) * world_unit_per_pixel
        new_position = old_position + offset
        self.position = (new_position.x, new_position.y, new_position.z)

    # Перемещает камеру вперед/назад относительно направления взгляда
    def dolly(self, offset_z: float) -> None:
        old_position = Vec3(*self.position)
        forward = Vec3(*self.forward)

        offset = forward * offset_z
        new_position = old_position + offset
        self.position = (new_position.x, new_position.y, new_position.z)

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
        current_position = Vec3(*self.position)
        forward = Vec3(*self.forward)
        pivot = current_position + forward * self.rotation_radius

        # 2. Локальные оси камеры для "экранного" вращения
        # Берём текущий вектор "вверх" камеры, чтобы вращение было относительным
        current_up = Vec3(*self.up)
        right = forward.cross(current_up).normalize()
        up = right.cross(forward).normalize()

        # 3. Углы поворота
        dx = -offset_x * self.settings.CAMERA_ROTATION_SENSITIVITY
        dy = offset_y * self.settings.CAMERA_ROTATION_SENSITIVITY

        # 4. Вектор от pivot до камеры
        v4 = Vec4(*(current_position - pivot), 1)

        # 5. Матрицы вращения
        rotation_horizontal = Mat4.from_rotation(dx, up)
        rotation_vertical = Mat4.from_rotation(dy, right)

        # Умножаем через @ и сразу вырезаем первые 3 компонента (xyz)
        # Сначала горизонталь, потом вертикаль
        v4 = rotation_vertical @ (rotation_horizontal @ v4)
        v_final = Vec3(v4.x, v4.y, v4.z)

        # 6. Обновляем позицию
        self.position = pivot + v_final

        # 7. Направляем камеру обратно на pivot
        # Передаем наш локальный 'up', чтобы картинка следовала за курсором без прыжков
        self.forward, self.up = arcade.camera.grips.look_at(self, pivot, up)

        self.axis_sort_order = tuple(sorted(range(3), key = lambda axis_index: abs(self.forward[axis_index])))

        max_index = max(range(3), key = lambda component: abs(self.forward[component]))
        forward_normal = [0] * 3
        forward_normal[0] = int(math.copysign(1, self.forward[max_index]))
        self.forward_normal = tuple(forward_normal)

        self.sort_direction = tuple(int(math.copysign(1, self.forward[index])) for index in self.axis_sort_order)


class ProjectProjector(PerspectiveProjector, ProjectMixin):
    view: ProjectCameraData

    def __init__(self, window: "ProjectWindow") -> None:
        camera_data = ProjectCameraData(self)
        super().__init__(window = window, view = camera_data)
        self.window = self._window
        # Увеличиваем дальность прорисовки в 10 раз, чтобы отрисовывалось больше объектов
        self.projection.far *= 10
        self.projection.fov = 20

    def init(self) -> None:
        # noinspection PyTypeChecker
        self.view.centralize(UIOnClickEvent(self, None, None, None, None))
