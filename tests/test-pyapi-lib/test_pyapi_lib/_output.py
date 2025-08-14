class OutputHandler:
    def __init__(self) -> None:
        self.print_handler = print

    def print(self, message: str) -> None:
        self.print_handler(message)


class Utils:
    @staticmethod
    def foo() -> str:
        return "bar"
