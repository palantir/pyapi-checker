from test_pyapi_lib._output import OutputHandler
from test_pyapi_lib.animals import Cat


def test_cat_has_four_legs() -> None:
    cat = Cat()
    assert cat.get_num_of_legs() == 4


def test_run_output_handler_print() -> None:
    output_handler = OutputHandler()
    output_handler.print("this is output")
