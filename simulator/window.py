import time
from collections import defaultdict, deque

import arcade
import arcade.gui
from arcade.future.input import MouseButtons
from arcade.gui import UIAnchorLayout, UIBoxLayout, UIManager

from core.gui.button import Button, DynamicTextButton
from core.gui.projector import Projector
from core.service.colors import ProjectColors
from core.service.object import ProjectMixin
from simulator.world import World


class Window(arcade.Window, ProjectMixin):

    def __init__(self, width: int, height: int) -> None:
        super().__init__(width, height, center_window = True)

        self.tps: int = 0
        self.desired_tps: int = 0
        self.set_tps(self.settings.MAX_TPS)
        self.previous_timestamp = time.time()
        self.timestamp = time.time()
        self.timings = defaultdict(lambda: deque(maxlen = self.settings.TIMINGS_LENGTH))

        self.world: World | None = None

        self.projector = Projector()
        self.ui_manager = UIManager(self)
        self.mouse_dragged = False

        arcade.set_background_color(ProjectColors.WHITE)

    def count_statistics(self) -> None:
        self.timings["tick"].append(self.timestamp - self.previous_timestamp)
        timings = self.timings["tick"]
        try:
            self.tps = int(len(timings) / sum(timings))
        except ZeroDivisionError:
            self.tps = self.desired_tps
        self.timings["tps"].append(self.tps)

    def set_tps(self, tps: int) -> None:
        self.desired_tps = tps
        self.set_update_rate(1 / tps)

    def start_interface(self) -> None:
        upper_right_corner_layout = UIBoxLayout()
        common_layout = UIAnchorLayout()
        common_layout.add(upper_right_corner_layout, anchor_x = "right", anchor_y = "top")

        centralize_camera_button = Button(text = "Поместить камеру по центру")
        centralize_camera_button.on_click = self.projector.centralize
        upper_right_corner_layout.add(centralize_camera_button)

        world_age_button = DynamicTextButton(
            text_function = lambda: f"Возраст мира: {self.world.age}",
            update_period = 0.01
        )
        upper_right_corner_layout.add(world_age_button)

        tps_button = DynamicTextButton(
            text_function = lambda: f"tps/желаемые tps: {self.tps} / {self.desired_tps}",
            update_period = 0.05
        )
        upper_right_corner_layout.add(tps_button)

        self.ui_manager.add(common_layout)

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

        self.start_interface()

    def stop(self) -> None:
        if self.world is not None:
            self.world.stop()

    def on_draw(self) -> None:
        self.clear()

        draw_faces = True
        draw_edges = True
        self.world.projection.on_draw(draw_faces, draw_edges)

        self.ui_manager.draw()

    def on_update(self, _: float) -> None:
        try:
            self.world.on_update(1)
        except Exception as error:
            error.window = self
            raise error
        finally:
            self.previous_timestamp = self.timestamp
            self.timestamp = time.time()
            self.count_statistics()

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if not self.mouse_dragged:
            if button == MouseButtons.LEFT.value:
                print(x, y)

        self.mouse_dragged = False

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> bool | None:
        # buttons - битовая маска.
        # Сравнивается ==, чтобы исключить действия при нажатии сразу нескольких кнопок
        if buttons == MouseButtons.LEFT.value:
            self.projector.move(dx, dy)
        elif buttons == MouseButtons.MIDDLE.value:
            # todo: реализовать вращение мира
            # todo: в camera.centralize добавить сброс добавленных параметров вращения
            print(f"rotate: {dx, dy}")
        self.mouse_dragged = True
        return None

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> bool | None:
        self.projector.change_zoom(x, y, scroll_x + scroll_y)
        return None
