from typing import Callable

from arcade.gui import UIFlatButton, UIOnClickEvent


class Button(UIFlatButton):
    pass


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


class DynamicTextButton(StatesButton):
    def __init__(self, text_function: Callable[[], str], **kwargs) -> None:
        super().__init__(**kwargs)

        self.text_function = text_function

    def on_update(self, delta_time: int) -> None:
        self.text = self.text_function()
