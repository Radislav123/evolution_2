import arcade

from core.pyglet import patch_gl
from simulator.window import ProjectWindow


def simulate() -> None:
    window = ProjectWindow()
    try:
        patch = False
        if patch:
            patch_gl()
        window.start()
        arcade.run()
    finally:
        window.stop()
        if window.world is not None:
            print(f"Симуляция окончена. Возраст мира: {window.world.age}")


if __name__ == "__main__":
    simulate()
