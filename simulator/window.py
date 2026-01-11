import time
from collections import defaultdict, deque

import arcade
import arcade.gui
from arcade.future.input import Keys, MouseButtons
from arcade.gui import UIAnchorLayout, UIBoxLayout, UIManager
from pyglet.event import EVENT_HANDLE_STATE

from core.gui.button import Button, DynamicTextButton
from core.gui.projector import ProjectProjector
from core.service.colors import ProjectColors
from core.service.object import ProjectMixin
from simulator.world import World


class ProjectWindow(arcade.Window, ProjectMixin):
    def __init__(self, width: int, height: int) -> None:
        super().__init__(width, height, center_window = True)

        self.tps: int = 0
        self.desired_tps: int = 0
        self.set_tps(self.settings.MAX_TPS)
        self.previous_timestamp = time.time()
        self.timestamp = time.time()
        self.timings = defaultdict(lambda: deque(maxlen = self.settings.TIMINGS_LENGTH))

        self.world: World | None = None

        self.projector = ProjectProjector(self)
        self.projector.init()
        self.ui_manager = UIManager(self)

        self.pressed_keys = set()
        self.mouse_dragged = False

        arcade.set_background_color(ProjectColors.BACKGROUND_LIGHT)

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
        centralize_camera_button.on_click = self.projector.view.centralize
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
        self.ui_manager.enable()
        self.world = World()

        self.world.start(self)
        self.world.projection.start()

        self.start_interface()

    def stop(self) -> None:
        if self.world is not None:
            self.world.stop()

    def on_draw(self) -> EVENT_HANDLE_STATE:
        self.clear()

        with self.projector.activate():
            draw_voxels = True
            self.world.projection.on_draw(draw_voxels)

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

    def on_key_press(self, symbol: int, modifiers: int) -> EVENT_HANDLE_STATE:
        self.pressed_keys.add(symbol)

    def on_key_release(self, symbol: int, modifiers: int) -> EVENT_HANDLE_STATE:
        self.pressed_keys.remove(symbol)

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> EVENT_HANDLE_STATE:
        if not self.mouse_dragged:
            if button == MouseButtons.LEFT.value:
                print(x, y)

        self.mouse_dragged = False

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> EVENT_HANDLE_STATE:
        # buttons - битовая маска.
        # Сравнивается ==, чтобы исключить действия при нажатии сразу нескольких кнопок
        if len(self.pressed_keys) == 0:
            if buttons == MouseButtons.LEFT.value:
                self.projector.view.pan(dx, dy)
        elif Keys.LCTRL.value in self.pressed_keys:
            if buttons == MouseButtons.LEFT.value:
                self.projector.view.rotate(dx, dy)

        self.mouse_dragged = True

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> EVENT_HANDLE_STATE:
        scroll = scroll_x + scroll_y
        if len(self.pressed_keys) == 0:
            self.projector.view.change_zoom(scroll)
        elif Keys.LCTRL.value in self.pressed_keys:
            self.projector.view.dolly(scroll)
