from arcade.camera import CameraData, PerspectiveProjector
from arcade.gui import UIOnClickEvent
from arcade.types import Point3

from core.service.object import ProjectMixin


class ProjectCameraData(CameraData, ProjectMixin):
    def __init__(
            self,
            position: Point3 = None,
            up: Point3 = None,
            forward: Point3 = None,
            zoom: float = None
    ) -> None:
        # todo: 500 заменить на значение, зависящее от размера мира, чтобы весь мир помещался на экране?
        # Отодвигаем камеру от (0, 0, 0) в (0, 0, 500), чтобы видеть объекты в центре сцены
        self.centralized_position = (10, 10, 500)
        if position is None:
            position = self.centralized_position
        if up is None:
            up = (0, 1, 0)
        if forward is None:
            forward = (0, 0, -1)
        if zoom is None:
            zoom = self.settings.CAMERA_INITIAL_ZOOM
        super().__init__(position, up, forward, zoom)


class Projector(PerspectiveProjector, ProjectMixin):
    view: ProjectCameraData

    def __init__(self) -> None:
        camera_data = ProjectCameraData()
        super().__init__(view = camera_data)
        # self.view: ProjectCameraData
        # Увеличиваем дальность прорисовки в 10 раз, чтобы отрисовывалось больше объектов
        self.projection.far *= 10

    def centralize(self, _: UIOnClickEvent) -> None:
        self.view.position = self.view.centralized_position
        self.view.zoom = self.settings.CAMERA_INITIAL_ZOOM

    def start(self) -> None:
        # noinspection PyTypeChecker
        self.centralize(UIOnClickEvent(self, None, None, None, None))

    def change_zoom(self, mouse_x: int, mouse_y: int, offset: float) -> None:
        scroll_coeff = self.settings.CAMERA_MAX_ZOOM / 10
        zoom_offset = offset * self.view.zoom / self.settings.CAMERA_MAX_ZOOM * scroll_coeff

        pre_zoom_position = self.unproject((mouse_x, mouse_y))
        self.view.zoom = max(
            min(self.view.zoom + zoom_offset, self.settings.CAMERA_MAX_ZOOM),
            self.settings.CAMERA_MIN_ZOOM
        )
        post_zoom_position = self.unproject((mouse_x, mouse_y))
        offset_x = post_zoom_position.x - pre_zoom_position.x
        offset_y = post_zoom_position.y - pre_zoom_position.y
        self.view.position = (
            self.view.position[0] - offset_x,
            self.view.position[1] - offset_y,
            self.view.position[2]
        )

    def move(self, offset_x: float, offset_y: float) -> None:
        self.view.position = (
            self.view.position[0] - offset_x / self.view.zoom,
            self.view.position[1] - offset_y / self.view.zoom,
            self.view.position[2]
        )
