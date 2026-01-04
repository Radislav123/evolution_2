import arcade
import arcade.gui
from arcade.future.input import MouseButtons
from arcade.gui import UIAnchorLayout, UIBoxLayout, UIManager

from core.gui.button import Button
from core.gui.projector import Projector
from core.service.colors import ProjectColors
from core.service.object import ObjectMixin
from simulator.world import World


class Window(arcade.Window, ObjectMixin):
    def __init__(self, width: int, height: int) -> None:
        super().__init__(width, height, center_window = True)

        self.world: World | None = None

        self.projector = Projector()
        self.ui_manager = UIManager(self)
        self.mouse_dragged = False

        arcade.set_background_color(ProjectColors.WHITE)

        # todo: remove shape_list
        self.shape_list = arcade.shape_list.ShapeElementList()
        shape = arcade.shape_list.create_rectangle_filled(100, 100, 100, 100, arcade.color.RED)
        self.shape_list.append(shape)

    def start(self) -> None:
        self.projector.use()
        self.ui_manager.enable()
        size = (
            (1, 1, 1),
            (5, 7, 9),
            (1, 2, 3),
            (2, 4, 6),
            (10, 10, 10),
            (3, 3, 3),
            (15, 15, 15),
            (25, 25, 25)
        )[6]
        self.world = World(*size)
        self.world.start()

        self.world.projection.start()
        self.projector.start()

        upper_right_corner_layout = UIBoxLayout()
        common_layout = UIAnchorLayout()
        common_layout.add(upper_right_corner_layout, anchor_x = "right", anchor_y = "top")

        centralize_camera_button = Button(
            text = "Поместить камеру по центру",
            width = self.settings.BUTTON_WIDTH,
            height = self.settings.BUTTON_HEIGHT
        )
        centralize_camera_button.on_click = self.projector.centralize
        upper_right_corner_layout.add(centralize_camera_button)

        self.ui_manager.add(common_layout)

    def stop(self) -> None:
        if self.world is not None:
            self.world.stop()

    def on_draw(self) -> None:
        self.clear()

        draw_faces = True
        draw_edges = True
        self.world.projection.on_draw(draw_faces, draw_edges)
        self.shape_list.draw()

        self.ui_manager.draw()

    def on_update(self, _: float) -> None:
        try:
            self.world.on_update(1)
        except Exception as error:
            error.window = self
            raise error
        finally:
            if self.world.age % 100 == 0:
                print(f"World age: {self.world.age}")

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if not self.mouse_dragged:
            if button == MouseButtons.LEFT.value:
                print(x, y)

        self.mouse_dragged = False

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> bool | None:
        # buttons - битовая маска.
        # Сравнивается ==, чтобы исключить действия при нажатии сразу нескольких кнопок
        if buttons == MouseButtons.LEFT.value:
            print(f"move: {dx, dy}")
            self.projector.move(dx, dy)
        elif buttons == MouseButtons.MIDDLE.value:
            # todo: реализовать вращение мира
            # todo: в camera.centralize добавить сброс добавленных параметров вращения
            print(f"rotate: {dx, dy}")
        self.mouse_dragged = True
        return None

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> bool | None:
        print(f"zoom: {scroll_x, scroll_y}")
        self.projector.change_zoom(x, y, scroll_x + scroll_y)
        return None
