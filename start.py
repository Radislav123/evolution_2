import arcade

from simulator.window import ProjectWindow


def simulate() -> None:
    window_width = 800
    window_height = 600

    window = ProjectWindow(window_width, window_height)
    try:
        window.start()
        arcade.run()
    finally:
        window.stop()
        if window.world is not None:
            print(f"Симуляция окончена. Возраст мира: {window.world.age}")


if __name__ == "__main__":
    simulate()
