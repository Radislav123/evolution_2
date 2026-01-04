from arcade import Camera2D

from core.service.object import ObjectMixin


class Camera(Camera2D, ObjectMixin):
    def __init__(self) -> None:
        super().__init__()

        # Центр мира
        self.center_position: tuple[float, float] | None = None

        self.min_zoom = self.settings.CAMERA_MIN_ZOOM
        self.max_zoom = self.settings.CAMERA_MAX_ZOOM
        self.initial_zoom = self.settings.CAMERA_INITIAL_ZOOM

    def centralize(self, center_x: float = None, center_y: float = None) -> None:
        if center_x is None or center_y is None:
            assert self.center_position is not None, "The first call must contain center position coordinates."
            center_x, center_y = self.center_position
        else:
            self.center_position = (center_x, center_y)

        self.zoom = self.initial_zoom
        self.position = (center_x, center_y)

    def start(self, center_x: float, center_y: float) -> None:
        self.centralize(center_x, center_y)

    def change_zoom(self, mouse_x: int, mouse_y: int, offset: float) -> None:
        scroll_coeff = self.max_zoom / 10
        zoom_offset = offset * self.zoom / self.max_zoom * scroll_coeff

        pre_zoom_position = self.unproject((mouse_x, mouse_y))
        self.zoom = max(min(self.zoom + zoom_offset, self.max_zoom), self.min_zoom)
        post_zoom_position = self.unproject((mouse_x, mouse_y))
        offset_x = post_zoom_position.x - pre_zoom_position.x
        offset_y = post_zoom_position.y - pre_zoom_position.y
        self.position = (self.position[0] - offset_x, self.position[1] - offset_y)

    def move(self, offset_x: float, offset_y: float) -> None:
        self.position = (self.position[0] - offset_x / self.zoom, self.position[1] - offset_y / self.zoom)
