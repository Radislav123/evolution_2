import math

import arcade
from arcade.camera import CameraData, PerspectiveProjector
from arcade.gui import UIOnClickEvent
from pyglet.math import Vec3

from core.service.object import ProjectMixin


class ProjectCameraData(CameraData, ProjectMixin):
    def __init__(self) -> None:
        self.rotation_radius = self.settings.CAMERA_ROTATION_RADIUS
        self.yaw: float = self.settings.CAMERA_YAW
        self.pitch: float = self.settings.CAMERA_PITCH

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

    def centralize(self, _: UIOnClickEvent) -> None:
        self.view.position = self.view.centralized_position
        self.view.zoom = self.settings.CAMERA_ZOOM

        self.view.yaw = self.settings.CAMERA_YAW
        self.view.pitch = self.settings.CAMERA_PITCH
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

    def change_zoom(self, mouse_x: int, mouse_y: int, offset: float) -> None:
        zoom_offset = offset * self.view.zoom * self.settings.CAMERA_ZOOM_SENSITIVITY

        self.view.zoom = max(
            min(self.view.zoom + zoom_offset, self.settings.CAMERA_MAX_ZOOM),
            self.settings.CAMERA_MIN_ZOOM
        )

    # Вращает камеру вокруг точки перед ней на расстоянии rotation_radius
    def rotate(self, offset_x: float, offset_y: float) -> None:
        self.view.yaw = (self.view.yaw + offset_x * self.settings.CAMERA_ROTATION_SENSITIVITY) % (math.pi * 2)
        self.view.pitch = (self.view.pitch + offset_y * self.settings.CAMERA_ROTATION_SENSITIVITY) % (math.pi * 2)

        pivot = Vec3(*self.view.position) + Vec3(*self.view.forward) * self.view.rotation_radius
        offset = Vec3(
            -self.view.rotation_radius * math.cos(self.view.pitch) * math.sin(self.view.yaw),
            -self.view.rotation_radius * math.sin(self.view.pitch),
            self.view.rotation_radius * math.cos(self.view.pitch) * math.cos(self.view.yaw)
        )

        self.view.position = pivot + offset
        self.view.forward, self.view.up = arcade.camera.grips.look_at(self.view, pivot)
