from arcade import Camera2D


class Camera(Camera2D):
    min_zoom = 0.01
    max_zoom = 500
    initial_zoom = 25

    def start(self, world_center_2: tuple[float, float]) -> None:
        self.zoom = self.initial_zoom
        self.position = world_center_2

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
