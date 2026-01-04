from arcade.camera import PerspectiveProjector
from arcade.gui import UIOnClickEvent

from core.service.object import ObjectMixin


class Projector(PerspectiveProjector, ObjectMixin):
    def __init__(self) -> None:
        super().__init__()
        # Увеличиваем дальность прорисовки в 10 раз, чтобы отрисовывалось больше объектов
        self.projection.far *= 10

        self.min_zoom = self.settings.CAMERA_MIN_ZOOM
        self.max_zoom = self.settings.CAMERA_MAX_ZOOM
        self.initial_zoom = self.settings.CAMERA_INITIAL_ZOOM

    def centralize(self, event: UIOnClickEvent) -> None:
        # todo: 500 заменить на значение, зависящее от размера мира, чтобы весь мир помещался на экране?
        # Отодвигаем камеру от (0, 0, 0) в (0, 0, 500), чтобы видеть объекты в центре сцены
        self.view.position = (0, 0, 500)

    def start(self) -> None:
        # noinspection PyTypeChecker
        self.centralize(UIOnClickEvent(self, None, None, None, None))

    # todo: remove method?
    def change_zoom(self, mouse_x: int, mouse_y: int, offset: float) -> None:
        return
        scroll_coeff = self.max_zoom / 10
        zoom_offset = offset * self.zoom / self.max_zoom * scroll_coeff

        pre_zoom_position = self.unproject((mouse_x, mouse_y))
        self.zoom = max(min(self.zoom + zoom_offset, self.max_zoom), self.min_zoom)
        post_zoom_position = self.unproject((mouse_x, mouse_y))
        offset_x = post_zoom_position.x - pre_zoom_position.x
        offset_y = post_zoom_position.y - pre_zoom_position.y
        self.position = (self.position[0] - offset_x, self.position[1] - offset_y)

    def move(self, offset_x: float, offset_y: float) -> None:
        # self.position = (self.position[0] - offset_x / self.zoom, self.position[1] - offset_y / self.zoom)
        self.view.position = (self.view.position[0] - offset_x, self.view.position[1] - offset_y, self.view.position[2])
