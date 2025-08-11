class Animal:
    def __init__(self, num_of_legs: int, is_mammal: bool = True) -> None:
        self.num_of_legs = num_of_legs
        self.is_mammal = is_mammal

    def get_num_of_legs(self) -> int:
        return self.num_of_legs

    def get_is_mammal(self) -> bool:
        return self.is_mammal


class Cat(Animal):
    def __init__(self) -> None:
        super().__init__(4)

    def meow(self) -> None:
        print("meow")
