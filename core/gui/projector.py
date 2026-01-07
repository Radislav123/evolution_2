import math

import arcade
from arcade.camera import CameraData, PerspectiveProjector
from arcade.gui import UIOnClickEvent
from pyglet.math import Mat4, Vec3, Vec4

from core.service.object import ProjectMixin


class ProjectCameraData(CameraData, ProjectMixin):
    def __init__(self) -> None:
        self.rotation_radius = self.settings.CAMERA_ROTATION_RADIUS

        # Отодвигаем камеру по z, чтобы видеть объекты в центре сцены
        self.centralized_position = (0, 0, self.rotation_radius)
        # Должен совпадать с World.center
        self.world_center = (0, 0, 0)

        super().__init__(position = self.centralized_position, zoom = self.settings.CAMERA_ZOOM)


class Projector(PerspectiveProjector, ProjectMixin):
    view: ProjectCameraData

    def __init__(self) -> None:
        camera_data = ProjectCameraData()
        super().__init__(view = camera_data)
        # Увеличиваем дальность прорисовки в 10 раз, чтобы отрисовывалось больше объектов
        self.projection.far *= 10
        self.projection.fov = 20

    def centralize(self, _: UIOnClickEvent) -> None:
        self.view.position = self.view.centralized_position
        self.view.zoom = self.settings.CAMERA_ZOOM

        self.view.forward, self.view.up = arcade.camera.grips.look_at(self.view, self.view.world_center)
        self.view.up = (0, 1, 0)

    def start(self) -> None:
        # noinspection PyTypeChecker
        self.centralize(UIOnClickEvent(self, None, None, None, None))

    # Перемещает камеру вправо/влево и вверх/вниз относительно направления взгляда
    def pan(self, offset_x: float, offset_y: float) -> None:
        old_position = Vec3(*self.view.position)
        forward = Vec3(*self.view.forward)
        up = Vec3(*self.view.up)
        right = forward.cross(up)

        distance = abs(old_position.dot(forward))
        fov_radian = math.radians(self.projection.fov)
        world_unit_per_pixel = (2 * distance * math.tan(fov_radian / 2)) / self._window.height / self.view.zoom

        offset = (right * -offset_x + up * -offset_y) * world_unit_per_pixel
        new_position = old_position + offset
        self.view.position = (new_position.x, new_position.y, new_position.z)

    # Перемещает камеру вперед/назад относительно направления взгляда
    def dolly(self, offset_z: float) -> None:
        old_position = Vec3(*self.view.position)
        forward = Vec3(*self.view.forward)

        offset = forward * offset_z
        new_position = old_position + offset
        self.view.position = (new_position.x, new_position.y, new_position.z)

    # Меняет зум и сдвигает картинку относительно курсора
    def change_zoom(self, offset: float) -> None:
        zoom_offset = offset * self.view.zoom * self.settings.CAMERA_ZOOM_SENSITIVITY

        self.view.zoom = max(
            min(self.view.zoom + zoom_offset, self.settings.CAMERA_MAX_ZOOM),
            self.settings.CAMERA_MIN_ZOOM
        )

    # Вращает камеру вокруг точки перед ней на расстоянии rotation_radius
    def rotate(self, offset_x: float, offset_y: float) -> None:
        # 1. Точка вращения и текущая позиция
        current_position = Vec3(*self.view.position)
        forward = Vec3(*self.view.forward)
        pivot = current_position + forward * self.view.rotation_radius

        # 2. Локальные оси камеры для "экранного" вращения
        # Берём текущий вектор "вверх" камеры, чтобы вращение было относительным
        current_up = Vec3(*self.view.up)
        right = forward.cross(current_up).normalize()
        up = right.cross(forward).normalize()

        # 3. Углы поворота
        dx = -offset_x * self.settings.CAMERA_ROTATION_SENSITIVITY
        dy = offset_y * self.settings.CAMERA_ROTATION_SENSITIVITY

        # 4. Вектор от pivot до камеры
        v4 = Vec4(*(current_position - pivot), 1.0)

        # 5. Матрицы вращения
        rot_h = Mat4.from_rotation(dx, up)
        rot_v = Mat4.from_rotation(dy, right)

        # Умножаем через @ и сразу вырезаем первые 3 компонента (xyz)
        # Сначала горизонталь, потом вертикаль
        v4 = rot_v @ (rot_h @ v4)
        v_final = Vec3(v4.x, v4.y, v4.z)

        # 6. Обновляем позицию
        self.view.position = pivot + v_final

        # 7. Направляем камеру обратно на pivot
        # Передаем наш локальный 'up', чтобы картинка следовала за курсором без прыжков
        self.view.forward, self.view.up = arcade.camera.grips.look_at(self.view, pivot, up)
