import time

import arcade
import arcade.gui
import numpy as np
from arcade.future.input import Keys, MouseButtons
from arcade.gui import UIAnchorLayout, UIBoxLayout, UIManager
from numpy import typing as npt
from pyglet import gl
from pyglet.event import EVENT_HANDLE_STATE

from core.gui.button import Button, DynamicTextButton
from core.gui.projector import ProjectProjector
from core.service.object import ProjectMixin
from simulator.world import World


TimingArray = npt.NDArray[np.float32]


class ProjectWindow(arcade.Window, ProjectMixin):
    tps_button: DynamicTextButton
    fps_button: DynamicTextButton

    def __init__(self) -> None:
        super().__init__(
            self.settings.WINDOW_WIDTH,
            self.settings.WINDOW_HEIGHT,
            self.settings.WINDOWS_TITLE,
            center_window = True
        )

        self.frame = 0
        self.tps = 0
        self.fps = 0
        self.desired_tps = 0
        self.desired_fps = 0
        self.timings: dict[str, list[TimingArray | int]] = {}
        self.set_tps(self.settings.MAX_TPS)
        self.set_fps(self.settings.MAX_FPS)

        timestamp = time.time()
        self.previous_tick_timestamp = timestamp
        self.tick_timestamp = timestamp
        self.previous_frame_timestamp = timestamp
        self.frame_timestamp = timestamp

        self.world: World | None = None

        self.projector = ProjectProjector(self)
        self.projector.init()
        self.ui_manager = UIManager(self)

        self.pressed_keys = set()
        self.mouse_dragged = False

        arcade.set_background_color(self.settings.WINDOW_BACKGROUND_COLOR)

    def set_tps(self, tps: int) -> None:
        self.desired_tps = tps
        self.set_update_rate(1 / tps)
        self.timings["tick"] = [np.zeros(self.desired_tps, dtype = np.float32), 0]
        self.timings["tps"] = [np.zeros(self.desired_tps * 10, dtype = np.int32), 0]

    def set_fps(self, fps: int) -> None:
        self.desired_fps = fps
        self.set_draw_rate(1 / fps)
        self.timings["frame"] = [np.zeros(self.desired_fps, dtype = np.float32), 0]
        self.timings["fps"] = [np.zeros(self.desired_fps * 10, dtype = np.int32), 0]

    def start_interface(self) -> None:
        upper_right_corner_layout = UIBoxLayout()
        common_layout = UIAnchorLayout()
        common_layout.add(upper_right_corner_layout, anchor_x = "right", anchor_y = "top")

        centralize_camera_button = Button(text = "Поместить камеру по центру")
        centralize_camera_button.on_click = self.projector.view.centralize
        upper_right_corner_layout.add(centralize_camera_button)

        world_age_button = DynamicTextButton(
            text_function = lambda: f"Возраст мира: {self.world.age}",
            update_period = 0.05
        )
        upper_right_corner_layout.add(world_age_button)

        self.tps_button = DynamicTextButton(
            text_function = lambda: f"tps: {self.tps} / {self.desired_tps}",
            update_period = 0.1
        )
        upper_right_corner_layout.add(self.tps_button)

        self.fps_button = DynamicTextButton(
            text_function = lambda: f"fps: {self.fps} / {self.desired_fps}",
            update_period = 0.5
        )
        upper_right_corner_layout.add(self.fps_button)

        self.ui_manager.add(common_layout)

    def start(self) -> None:
        features_to_disable = (
            gl.GL_DEPTH_TEST,
            gl.GL_STENCIL_TEST,
            gl.GL_CULL_FACE,
            gl.GL_BLEND,
            gl.GL_MULTISAMPLE
        )
        for feature in features_to_disable:
            gl.glDisable(feature)

        self.ui_manager.enable()
        self.world = World(self)

        self.world.start()
        self.world.projection.start()

        self.start_interface()

        # Для ожидания записи в буферы
        gl.glMemoryBarrier(gl.GL_SHADER_STORAGE_BARRIER_BIT)

    def stop(self) -> None:
        if self.world is not None:
            self.world.stop()

    def update_timing(self, timing: str, value: float | int) -> TimingArray:
        timing_array, index = self.timings[timing]
        timing_array[index] = value

        self.timings[timing][1] = (index + 1) % timing_array.size
        return timing_array

    def count_statistics_tps(self) -> None:
        timings = self.update_timing("tick", self.tick_timestamp - self.previous_tick_timestamp)
        self.tps = int(timings.size / timings.sum())
        self.update_timing("tps", self.tps)

    def count_statistics_fps(self) -> None:
        timings = self.update_timing("frame", self.frame_timestamp - self.previous_frame_timestamp)
        self.fps = int(timings.size / timings.sum())
        self.update_timing("fps", self.fps)

    def on_update(self, _: float) -> None:
        try:
            self.world.on_update()
        except Exception as error:
            error.window = self
            raise error
        finally:
            if self.tps_button.state == 0:
                self.previous_tick_timestamp = self.tick_timestamp
                self.tick_timestamp = time.time()
                self.count_statistics_tps()

    def on_draw(self) -> EVENT_HANDLE_STATE:
        try:
            self.clear()

            with self.projector.activate():
                draw_voxels = True
                self.world.projection.on_draw(draw_voxels)

            self.ui_manager.draw()
            self.frame += 1
        except Exception as error:
            error.window = self
            raise error
        finally:
            if self.fps_button.state == 0:
                self.previous_frame_timestamp = self.frame_timestamp
                self.frame_timestamp = time.time()
                self.count_statistics_fps()

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
