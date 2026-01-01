import enum
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable, Iterator

import arcade
import arcade.gui
from arcade import color, uicolor
from arcade.future.input import MouseButtons
from arcade.types import Color
from matplotlib import pyplot

from core.service.object import Mixin
from simulator.world import World


class TextTab(arcade.gui.UIFlatButton, Mixin):
    default_style = {
        "normal": arcade.gui.UIFlatButton.UIStyle(
            bg = color.BLACK
        ),
        "hover": arcade.gui.UIFlatButton.UIStyle(
            font_color = color.WHITE,
            bg = Color(*(50 for _ in range(3))),
            border = uicolor.GRAY_CONCRETE
        ),
        "press": arcade.gui.UIFlatButton.UIStyle(
            font_color = uicolor.DARK_BLUE_MIDNIGHT_BLUE,
            bg = uicolor.WHITE_CLOUDS,
            border = uicolor.GRAY_CONCRETE
        ),
        "disabled": arcade.gui.UIFlatButton.UIStyle(
            font_color = uicolor.WHITE_SILVER,
            bg = uicolor.GRAY_ASBESTOS
        )
    }

    class State(enum.Enum):
        NOT_PRESSED = 0
        PRESSED = 1

        @property
        def next(self) -> "TextTab.State":
            return self.__class__((self.value + 1) % len(self.__class__))

        def __str__(self) -> str:
            if self == self.NOT_PRESSED:
                string = "[  ]"
            elif self == self.PRESSED:
                string = "[x]"
            else:
                raise ValueError()
            return string

    class Label(arcade.Text):
        def __init__(self, tab: "TextTab", text: Callable[[], str], update_period: int, *args, **kwargs) -> None:
            self.tab = tab
            self._text = text
            # количество тиков между обновлением текста
            self.update_period = update_period

            super().__init__(tab.text, 0, 0, color = color.BLACK, *args, **kwargs)

        def set_position(self) -> None:
            offset_x = -10
            offset_y = -5
            if self.tab.corner.index in [0, 1]:
                start_x = self.tab.rect.x + self.tab.width + offset_x
                anchor_x = "left"
            else:
                start_x = self.tab.rect.x - offset_x + 3 * offset_x
                anchor_x = "right"
            start_y = self.tab.rect.y + offset_y
            anchor_y = "baseline"

            self.x = start_x
            self.y = start_y
            self.anchor_x = anchor_x
            self.anchor_y = anchor_y

    def __init__(self, text: Callable[[], str], update_period: int) -> None:
        # text передается для инициализации ui_label
        super().__init__(text = str(self.State.PRESSED), style = self.default_style)

        self.update_period = update_period
        self.state: TextTab.State | None = None
        self.set()
        self.corner: TextTabContainer.Corner | None = None
        border = 10
        self.rect = self.rect.resize(round(self.ui_label.width) + border, round(self.ui_label.height) + border)
        self.tab_label = self.Label(self, text, self.update_period)

    def __bool__(self) -> bool:
        return self.state == self.State.PRESSED

    def set(self) -> None:
        self.state = self.State.PRESSED
        self.update_text()

    def reset(self) -> None:
        self.state = self.State.NOT_PRESSED
        self.update_text()

    def on_click(self, event: arcade.gui.UIOnClickEvent = None) -> None:
        if self.state == self.State.PRESSED:
            self.reset()
        else:
            self.set()
        self.update_text()

    def update_text(self) -> None:
        self.text = str(self.state)


class DrawGraphsTab(TextTab):
    def set(self) -> None:
        super().set()
        arcade.enable_timings()

    def reset(self) -> None:
        super().reset()
        try:
            arcade.disable_timings()
        except ValueError:
            # при отключении всегда выбрасывается исключение
            pass


class TextTabContainer(Mixin):
    class Corner(arcade.gui.UIAnchorLayout):
        children: list[TextTab]

        def __init__(self, container: "TextTabContainer", index: int, *args, **kwargs) -> None:
            self.container = container
            self.index = index
            super().__init__(*args, **kwargs)

        def add(self, child: TextTab, **kwargs) -> TextTab:
            child.corner = self
            child.corner_position = len(self.children)

            if self.index in [0, 1]:
                anchor_x = "left"
            else:
                anchor_x = "right"
            if self.index in [0, 2]:
                anchor_y = "bottom"
                align_y = sum(map(lambda x: x.height, self.children))
            else:
                anchor_y = "top"
                align_y = -sum(map(lambda x: x.height, self.children))

            result = super().add(child, anchor_x = anchor_x, anchor_y = anchor_y, align_y = align_y, **kwargs)
            self.container.tabs.add(result)
            self.container.tab_update_periods[result.update_period].add(result)

            return result

    def __init__(self, window: "Window") -> None:
        super().__init__()
        self.window = window
        # 00 - левый нижний угол (corners[0])
        # 01 - левый верхний угол (corners[1])
        # 10 - правый нижний угол (corners[2])
        # 11 - правый верхний угол (corners[3])
        # 01 11
        # 00 10
        # 1 3
        # 0 2
        # tab_container[n] = [tab_0, tab_1,..]
        self.corners: tuple[
            TextTabContainer.Corner,
            TextTabContainer.Corner,
            TextTabContainer.Corner,
            TextTabContainer.Corner
        ] = (
            self.Corner(self, 0),
            self.Corner(self, 1),
            self.Corner(self, 2),
            self.Corner(self, 3)
        )
        self.tabs: set[TextTab] = set()
        self.tab_update_periods: defaultdict[int, set[TextTab]] = defaultdict(set)

    def __iter__(self) -> Iterator[TextTab]:
        return iter(self.tabs)

    def draw_all(self) -> None:
        for tab in self.tabs:
            if tab.state == tab.State.PRESSED:
                # todo: переписать так, чтобы отрисовывать все активные плашки одним вызовом
                tab.tab_label.draw()

    def update_all(self) -> None:
        for update_period, tabs in self.tab_update_periods.items():
            if self.window.world.age % update_period == 0:
                for tab in tabs:
                    if tab.state == tab.State.PRESSED:
                        # noinspection PyProtectedMember 
                        tab.tab_label.text = tab.tab_label._text()


class UIManager(arcade.gui.UIManager, Mixin):
    def add_tabs(self, tabs: TextTabContainer) -> TextTabContainer:
        for corner in tabs.corners:
            self.add(corner)

        return tabs

    @staticmethod
    def set_tab_label_positions(tabs: TextTabContainer) -> None:
        for corner in tabs.corners:
            for tab in corner.children:
                tab.tab_label.set_position()


class PerformanceGraph(arcade.PerfGraph, Mixin):
    def __init__(self, window: "Window", *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.window = window

    def update_graph(self, delta_time: float):
        # Skip update if there is no SpriteList that can draw this graph
        if self.sprite_lists is None or len(self.sprite_lists) == 0:
            return

        sprite_list = self.sprite_lists[0]

        # Clear and return if timings are disabled
        if not arcade.timings_enabled():
            with sprite_list.atlas.render_into(self.minimap_texture, projection = self.proj) as fbo:
                fbo.clear(color = (0, 0, 0, 255))
            return

        # Get FPS and add to our historical data
        data_to_graph = self._data_to_graph
        graph_data = self.graph_data
        timings = self.window.timings
        if graph_data in timings:
            timing_list = timings[self.graph_data]
            avg_timing = sum(timing_list) / len(timing_list)
            if graph_data == "tps":
                data_to_graph.append(avg_timing)
            else:
                data_to_graph.append(avg_timing * 1000)

        # Skip update if there is no data to graph
        if len(data_to_graph) == 0:
            return

        # Using locals for frequently used values is faster than
        # looking up instance variables repeatedly.
        bottom_y = self._bottom_y
        left_x = self._left_x
        view_y_scale_step = self._view_y_scale_step
        vertical_axis_text_objects = self._vertical_axis_text_objects
        view_height = self._view_height

        # We have to render at the internal texture's original size to
        # prevent distortion and bugs when the projection is scaled.
        texture_width, texture_height = self._texture.size  # type: ignore

        # Toss old data by removing leftmost entries
        while len(data_to_graph) > texture_width - left_x:
            data_to_graph.pop(0)

        # Calculate the value at the top of the chart
        max_value = max(data_to_graph)
        view_max_value = ((max_value + 1.5) // view_y_scale_step + 1) * view_y_scale_step

        # Calculate draw positions of each pixel on the data line
        point_list = []
        x = left_x
        for reading in data_to_graph:
            y = (reading / view_max_value) * view_height + bottom_y
            point_list.append((x, y))
            x += 1

        # Update the view scale & labels if needed
        if view_max_value != self._view_max_value:
            self._view_max_value = view_max_value
            view_y_legend_increment = self._view_max_value // self._y_axis_num_lines
            for index in range(1, len(vertical_axis_text_objects)):
                text_object = vertical_axis_text_objects[index]
                text_object.text = f"{int(index * view_y_legend_increment)}"

        # Render to the internal texture
        with sprite_list.atlas.render_into(self.minimap_texture, projection = self.proj) as fbo:

            # Set the background color
            fbo.clear(self.background_color)

            # Draw lines & their labels
            for text in self._all_text_objects:
                text.draw()
            self._pyglet_batch.draw()

            # Draw the data line
            arcade.draw_line_strip(point_list, self.line_color)


class Window(arcade.Window, Mixin):
    # desired_tps = int(1 / update_rate)
    # update_rate = 1 / tps
    desired_tps: int
    creature_resources_tab: TextTab
    base_resources_tab: TextTab
    world_resources_tab: TextTab
    # отрисовка сетки мира
    draw_tiles_tab: TextTab
    draw_objects_tab: TextTab
    draw_graphs_tab: TextTab
    creature_tps_statistics: dict["Creature", list[int]] = defaultdict(list)

    def __init__(self, width: int, height: int) -> None:
        super().__init__(width, height, center_window = True)

        self.world: World | None = None
        self.tab_container = TextTabContainer(self)
        self.set_tps(self.settings.MAX_TPS)
        self.tps = self.settings.MAX_TPS
        self.previous_timestamp = time.time()
        self.timestamp = time.time()
        self.creature_resources = 0
        self.base_resources = 0
        self.world_resources = 0

        self.ui_manager = UIManager(self)
        self.graphs = arcade.SpriteList()
        self.mouse_dragged = False

        background_color = (255, 255, 255, 255)
        arcade.set_background_color(background_color)

        self.timings = defaultdict(lambda: deque(maxlen = self.settings.TIMINGS_LENGTH))

    def start(self) -> None:
        self.world = World(3, 3, 3)
        self.world.start()

        self.world.projection.start()

        self.construct_tabs()
        self.construct_graphs()

        # необходимо, чтобы разместить плашки, так как элементы размещаются на экране только после первой отрисовки
        self.on_draw()
        self.ui_manager.set_tab_label_positions(self.tab_container)

        self.ui_manager.enable()

    def stop(self) -> None:
        if self.world is not None:
            self.world.stop()

        make_plot = False
        if make_plot:
            # подготовка статистики
            creature_tps = {x: sum(self.creature_tps_statistics[x]) / len(self.creature_tps_statistics[x])
                            for x in sorted(self.creature_tps_statistics)}

            pyplot.plot(list(creature_tps.keys()), list(creature_tps.values()), color = "r")
            max_creatures = list(creature_tps.keys())[-1]
            max_tps = max(list(creature_tps.values()))
            pyplot.xlim(xmin = 0, xmax = max_creatures)
            pyplot.ylim(ymin = 0, ymax = max_tps)
            points_amount = 5
            step = max(max_creatures // points_amount, 1)
            # for creatures in range(step, max_creatures, step):
            for creatures in range(max_creatures, max_creatures, step):
                x = creatures
                while x not in creature_tps and x > 0:
                    x -= 1
                y = int(creature_tps[x])
                line_width = 0.8
                color = "g"
                pyplot.axhline(
                    y = y,
                    xmin = 0,
                    xmax = x / max_creatures,
                    linewidth = line_width,
                    color = color
                )
                pyplot.axvline(
                    x = x,
                    ymin = 0,
                    ymax = creature_tps[x] / max_tps,
                    linewidth = line_width,
                    color = color
                )
                pyplot.text(x, y, f"({x}; {y})")  # noqa
            pyplot.title("Зависимость tps от количества существ")
            pyplot.xlabel("Существа")
            pyplot.ylabel("tps")

            # сохранение статистики
            folder = f"statistics/creatures_tps"
            Path(folder).mkdir(parents = True, exist_ok = True)
            pyplot.savefig(f"{folder}/plot.png")

    def construct_graphs(self) -> None:
        # ((graph_name, is_custom),..)
        graph_statistics = (
            ("FPS", False),
            ("on_draw", False),
            ("tps", True),
            ("on_update", True),
        )

        left = 0
        top = self.height - 90
        width = 190
        height = (top - 90) // len(graph_statistics)

        counter = 0
        for graph_name, is_custom in graph_statistics:
            if is_custom:
                graph = PerformanceGraph(self, width, height, graph_name)
            else:
                graph = arcade.PerfGraph(width, height, graph_name)
            graph.left = left
            graph.top = top - height * counter
            self.graphs.append(graph)
            counter += 1

    def construct_tabs(self) -> None:
        # правый верхний угол
        # возраст мира
        self.tab_container.corners[3].add(
            TextTab(lambda: str(self.world.age), self.settings.WORLD_AGE_TAB_UPDATE_PERIOD)
        )
        # счетчик tps
        self.tab_container.corners[3].add(
            TextTab(
                lambda: f"tps/желаемые tps: {self.tps} / {self.desired_tps}",
                self.settings.TPS_TAB_UPDATE_PERIOD
            )
        )
        # отображение графиков
        self.draw_graphs_tab = self.tab_container.corners[3].add(
            DrawGraphsTab(lambda: "Отображать графики", self.settings.TPS_TAB_UPDATE_PERIOD)
        )
        self.draw_graphs_tab.reset()

        # правый нижний угол

        # левый верхний угол
        self.world_resources_tab = self.tab_container.corners[1].add(
            TextTab(lambda: f"Ресурсы в мире: {self.world_resources}", self.settings.RESOURCES_TAB_UPDATE_PERIOD)
        )
        self.base_resources_tab = self.tab_container.corners[1].add(
            TextTab(lambda: f"Ресурсы на карте: {self.base_resources}", self.settings.RESOURCES_TAB_UPDATE_PERIOD)
        )
        self.creature_resources_tab = self.tab_container.corners[1].add(
            TextTab(lambda: f"Ресурсы существ: {self.creature_resources}", self.settings.RESOURCES_TAB_UPDATE_PERIOD)
        )

        # левый нижний угол
        # отрисовка сетки
        self.draw_tiles_tab = self.tab_container.corners[0].add(
            TextTab(lambda: "Показывать сетку мира", self.settings.OVERLAY_UPDATE_PERIOD)
        )
        # отрисовка объектов
        self.draw_objects_tab = self.tab_container.corners[0].add(
            TextTab(lambda: "Показывать существ", self.settings.OVERLAY_UPDATE_PERIOD)
        )

        self.count_resources()
        self.tab_container.update_all()

        self.ui_manager.add_tabs(self.tab_container)

    def count_resources(self) -> None:
        if self.creature_resources_tab or self.world_resources_tab:
            pass
            # self.creature_resources = sum((x.resources for x in self.world.creatures))

    def count_statistics(self) -> None:
        self.timings["on_update"].append(self.timestamp - self.previous_timestamp)
        timings = self.timings["on_update"]
        try:
            self.tps = int(len(timings) / sum(timings))
        except ZeroDivisionError:
            self.tps = self.desired_tps
        self.timings["tps"].append(self.tps)

        # self.creature_tps_statistics[len(self.world.creatures)].append(self.tps)
        self.creature_tps_statistics[1].append(self.tps)

    def on_draw(self) -> None:
        self.clear()

        draw_objects = bool(self.draw_objects_tab)
        draw_tiles = bool(self.draw_tiles_tab)
        self.world.projection.on_draw(draw_tiles)

        self.ui_manager.draw()
        self.tab_container.draw_all()

        if self.draw_graphs_tab:
            self.graphs.draw()

    def on_update(self, _: float) -> None:
        try:
            self.world.on_update(1)
            self.tab_container.update_all()
        except Exception as error:
            error.window = self
            raise error
        finally:
            if self.world.age % self.settings.TAB_UPDATE_PERIOD == 0:
                self.count_resources()
            self.previous_timestamp = self.timestamp
            self.timestamp = time.time()
            self.count_statistics()

    def set_tps(self, tps: int) -> None:
        self.desired_tps = tps
        self.set_update_rate(1 / tps)

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if not self.mouse_dragged and self.draw_tiles_tab:
            if button == MouseButtons.LEFT.value:
                print(x, y)

        self.mouse_dragged = False

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> bool | None:
        if buttons & MouseButtons.LEFT.value:
            self.world.projection.change_offset(dx, dy)
        self.mouse_dragged = True
        return None

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> bool | None:
        self.world.projection.change_coeff(x, y, scroll_y + scroll_x)
        return None
