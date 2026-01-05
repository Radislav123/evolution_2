import time
from typing import Callable

from arcade.gui import UIFlatButton, UIOnClickEvent

from core.service.object import ProjectMixin


class Button(UIFlatButton, ProjectMixin):
    def __init__(self, width: float = None, height: float = None, **kwargs) -> None:
        if width is None:
            width = self.settings.BUTTON_WIDTH
        if height is None:
            height = self.settings.BUTTON_HEIGHT
        super().__init__(width = width, height = height, **kwargs)


class StatesButton(Button):
    def __init__(self, state_count: int = 2, state_to_text: list[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.state_count = state_count
        if state_to_text is None:
            state_to_text = [f"state_{index}" for index in range(self.state_count)]
        self.state_to_text = state_to_text
        assert self.state_count == len(self.state_to_text), "state_count must be equal to state_to_text length"

        self.state: int = 0
        self.text: str = ""
        self.update_state(0)

    def update_state(self, offset: int = 1) -> None:
        self.state = (self.state + offset) % self.state_count
        self.text = self.state_to_text[self.state]

    def on_click(self, event: UIOnClickEvent) -> None:
        self.update_state()


# todo: Обновление текста на кнопке очень затратная операция - нужно ускорить это
class DynamicTextButton(StatesButton):
    def __init__(
            self,
            text_function: Callable[[], str],
            update_period: float = None,
            state_count: int = 2,
            state_to_text: list[str] = None,
            **kwargs
    ) -> None:
        if state_to_text is None:
            state_to_text = ["" for _ in range(state_count)]
        super().__init__(state_count = state_count, state_to_text = state_to_text, **kwargs)

        self.text_function = text_function
        if update_period is None:
            update_period = self.settings.BUTTON_UPDATE_PERIOD
        self.update_period = update_period
        # Метка последнего обновления
        self.update_timestamp: float = 0

    def on_update(self, delta_time: int) -> None:
        timestamp = time.time()
        if self.state == 0 and (timestamp - self.update_timestamp) >= self.update_period:
            self.text = self.text_function()
            self.update_timestamp = timestamp
