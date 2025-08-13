"""
Copyright 2025 Palantir Technologies, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

from pyapi.app import PyAPIApplication
from pyapi.color import ANSIColor
from pyapi.constants import PYAPI_YML_FILENAME, PYAPI_YML_PATH


def test_analyze_no_code_change(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    app = PyAPIApplication(test_lib_path)

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    app.analyze()

    assert captured_output.getvalue() == "No Python API breaks found.\n"

    sys.stdout = sys.__stdout__  # Reset stdout


def test_analyze_no_breaks(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    app = PyAPIApplication(test_lib_path)
    animals_path = test_lib_path / "test_pyapi_lib/animals.py"
    animals_path.write_text(
        animals_path.read_text().replace(
            'def meow(self) -> None:\n        print("meow")',
            'def meow(self) -> None:\n        print("meow")\n\ndef purr(self) -> None:\n        print("purr")',
        )
    )

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    app.analyze()

    assert captured_output.getvalue() == "No Python API breaks found.\n"

    sys.stdout = sys.__stdout__  # Reset stdout


def test_analyze_with_break(test_lib: tuple[Path, MagicMock], monkeypatch: MonkeyPatch) -> None:
    test_lib_path, _ = test_lib
    monkeypatch.delenv("CI", raising=False)
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    app = PyAPIApplication(test_lib_path)

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    with pytest.raises(SystemExit) as cm:
        app.analyze()

    assert cm.value.code == 1
    assert captured_output.getvalue() == (
        f"{ANSIColor.RED_UNDERLINED.value}\nPython API breaks found in test-pyapi-lib:{ANSIColor.NO_COLOR.value}\n"
        f"{ANSIColor.RED_HIGH_INTENSITY.value}AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.{ANSIColor.NO_COLOR.value}\n"
        "You can accept an API break via:\n"
        f'{ANSIColor.CYAN.value}  pyapi acceptBreak "AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c." ":justification:"{ANSIColor.NO_COLOR.value}\n'
        "or all API breaks via:\n"
        f'{ANSIColor.CYAN.value}  pyapi acceptAllBreaks ":justification:"{ANSIColor.NO_COLOR.value}\n'
    )

    sys.stdout = sys.__stdout__  # Reset stdout


def test_analyze_with_multiple_breaks(test_lib: tuple[Path, MagicMock], monkeypatch: MonkeyPatch) -> None:
    test_lib_path, _ = test_lib
    monkeypatch.setenv("CI", "true")
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: str, b: str)", "(a: int)"))
    animals_path = test_lib_path / "test_pyapi_lib/animals.py"
    animals_path.write_text(
        animals_path.read_text()
        .replace('def meow(self) -> None:\n        return self._vocalize("meow")', "")
        .replace("is_mammal: bool = True", "is_mammal: bool")
    )
    app = PyAPIApplication(test_lib_path)

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    with pytest.raises(SystemExit) as cm:
        app.analyze()

    assert cm.value.code == 1
    assert captured_output.getvalue() == (
        "\nPython API breaks found in test-pyapi-lib:\n"
        "RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False.\n"
        "RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): meow\n"
        "RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.\n"
        "ChangeParameterType: Change parameter type (test_pyapi_lib.functions.special_string_add): a: builtins.str => builtins.int\n"
        "You can accept an API break via:\n"
        '  pyapi acceptBreak "RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False." ":justification:"\n'
        "or all API breaks via:\n"
        '  pyapi acceptAllBreaks ":justification:"\n'
    )

    sys.stdout = sys.__stdout__  # Reset stdout


@pytest.mark.parametrize("test_lib", [{"current_git_version": b"1.0.0"}], indirect=True)
def test_analyze_on_release_version(test_lib: tuple[Path, MagicMock], monkeypatch: MonkeyPatch) -> None:
    test_lib_path, _ = test_lib
    monkeypatch.setenv("CI", "true")
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: str, b: str)", "(a: int)"))
    app = PyAPIApplication(test_lib_path)

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    app.analyze()

    assert (
        captured_output.getvalue()
        == "Current version is the same as the previous version, this is a release version, skipping analysis.\n"
    )

    sys.stdout = sys.__stdout__  # Reset stdout


def test_analyze_with_version_override(test_lib: tuple[Path, MagicMock], monkeypatch: MonkeyPatch) -> None:
    test_lib_path, _ = test_lib
    monkeypatch.setenv("CI", "true")
    app = PyAPIApplication(test_lib_path)
    pyapi_yml_file = test_lib_path / ".." / PYAPI_YML_PATH
    (test_lib_path / ".." / ".palantir").mkdir()
    pyapi_yml_file.write_text("acceptedBreaks: {}\nversionOverrides:\n  1.0.0: 0.9.0\n")

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    # Just check that it tries to download the correct version, this wheel doesn't exist so it will fail.
    with pytest.raises(SystemExit) as cm:
        app.analyze()

    assert cm.value.code == 1
    output = captured_output.getvalue()
    assert "Failed to download test-pyapi-lib 0.9.0 from Python index." in output
    assert (
        "If the above version was tagged but failed to publish, apply a version override via:\n  pyapi versionOverride <last-published-version>\n"
        in output
    )

    sys.stdout = sys.__stdout__  # Reset stdout


def test_accept_break_with_break(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    pyapi_yml_path = test_lib_path / ".." / PYAPI_YML_PATH
    assert not pyapi_yml_path.exists()
    app = PyAPIApplication(test_lib_path)

    app.accept_break(
        "AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.",
        "basic justification",
    )

    assert (
        pyapi_yml_path.read_text()
        == "acceptedBreaks:\n  1.0.0:\n    test-pyapi-lib:\n    - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'\n"
        "      justification: basic justification\nversionOverrides: {}\n"
    )


def test_accept_break_with_multiple_breaks(test_lib: tuple[Path, MagicMock], monkeypatch: MonkeyPatch) -> None:
    test_lib_path, _ = test_lib
    monkeypatch.setenv("CI", "true")
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: str, b: str)", "(a: int)"))
    animals_path = test_lib_path / "test_pyapi_lib/animals.py"
    animals_path.write_text(
        animals_path.read_text()
        .replace('def meow(self) -> None:\n        return self._vocalize("meow")', "")
        .replace("is_mammal: bool = True", "is_mammal: bool")
    )
    pyapi_yml_path = test_lib_path / ".." / PYAPI_YML_PATH
    assert not pyapi_yml_path.exists()
    app = PyAPIApplication(test_lib_path)

    app.accept_break(
        "RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): meow",
        "meow is never used",
    )

    assert (
        pyapi_yml_path.read_text()
        == "acceptedBreaks:\n  1.0.0:\n    test-pyapi-lib:\n    - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): meow'\n      justification: meow is never used\n"
        "versionOverrides: {}\n"
    )

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    app = PyAPIApplication(test_lib_path)  # Recreate app for new command.
    with pytest.raises(SystemExit) as cm:
        app.analyze()

    assert cm.value.code == 1
    assert captured_output.getvalue() == (
        "\nPython API breaks found in test-pyapi-lib:\n"
        "RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False.\n"
        "RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.\n"
        "ChangeParameterType: Change parameter type (test_pyapi_lib.functions.special_string_add): a: builtins.str => builtins.int\n"
        "You can accept an API break via:\n"
        '  pyapi acceptBreak "RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False." ":justification:"\n'
        "or all API breaks via:\n"
        '  pyapi acceptAllBreaks ":justification:"\n'
    )

    sys.stdout = sys.__stdout__  # Reset stdout


def test_accept_break_that_is_already_accepted(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_text = (
        "acceptedBreaks:\n  1.0.0:\n    test-pyapi-lib:\n    - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'\n"
        "      justification: previous acceptance\nversionOverrides: {}\n"
    )
    pyapi_yml_path.write_text(pyapi_yml_text)
    app = PyAPIApplication(test_lib_path)

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    app.accept_break(
        "AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.",
        "basic justification",
    )

    assert (
        captured_output.getvalue()
        == "Break 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.' is already accepted\n"
    )

    assert pyapi_yml_path.read_text() == pyapi_yml_text

    sys.stdout = sys.__stdout__  # Reset stdout


def test_accept_break_invalid_break(test_lib: tuple[Path, MagicMock], monkeypatch: MonkeyPatch) -> None:
    test_lib_path, _ = test_lib
    monkeypatch.delenv("CI", raising=False)
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    app = PyAPIApplication(test_lib_path)

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    with pytest.raises(SystemExit) as cm:
        app.accept_break("a break", "my just")

    assert cm.value.code == 1
    assert (
        captured_output.getvalue()
        == f"{ANSIColor.RED.value}\nBreak 'a break' is not a valid Python API break and cannot be accepted{ANSIColor.NO_COLOR.value}\n"
    )


def test_accept_all_breaks_with_break(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    pyapi_yml_path = test_lib_path / ".." / PYAPI_YML_PATH
    assert not pyapi_yml_path.exists()
    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("basic justification")

    assert (
        pyapi_yml_path.read_text()
        == "acceptedBreaks:\n  1.0.0:\n    test-pyapi-lib:\n    - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'\n"
        "      justification: basic justification\nversionOverrides: {}\n"
    )


def test_accept_all_breaks_with_multiple_breaks(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: str, b: str)", "(a: int)"))
    animals_path = test_lib_path / "test_pyapi_lib/animals.py"
    animals_path.write_text(
        animals_path.read_text()
        .replace('def meow(self) -> None:\n        return self._vocalize("meow")', "")
        .replace("is_mammal: bool = True", "is_mammal: bool")
    )
    pyapi_yml_path = test_lib_path / ".." / PYAPI_YML_PATH
    assert not pyapi_yml_path.exists()
    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("these are all irrelevant")

    assert pyapi_yml_path.read_text() == (
        "acceptedBreaks:\n  1.0.0:\n    test-pyapi-lib:\n"
        "    - code: 'RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False.'\n      justification: these are all irrelevant\n"
        "    - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): meow'\n      justification: these are all irrelevant\n"
        "    - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'\n      justification: these are all irrelevant\n"
        "    - code: 'ChangeParameterType: Change parameter type (test_pyapi_lib.functions.special_string_add): a: builtins.str => builtins.int'\n      justification: these are all irrelevant\n"
        "versionOverrides: {}\n"
    )


def test_accept_all_breaks_with_break_and_existing_accepted(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_path.write_text(
        (
            "acceptedBreaks:\n  0.191.0:\n    test-pyapi-lib:\n    - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'\n      justification: no purrs allowed\n"
            "  1.0.0:\n    test-pyapi-lib:\n    - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'\n      justification: previous acceptance\n"
            "versionOverrides: {}\n"
        )
    )
    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("basic justification")

    assert pyapi_yml_path.read_text() == (
        "acceptedBreaks:\n  0.191.0:\n    test-pyapi-lib:\n    - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'\n      justification: no purrs allowed\n"
        "  1.0.0:\n    test-pyapi-lib:\n    - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'\n      justification: previous acceptance\n"
        "    - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'\n      justification: basic justification\n"
        "versionOverrides: {}\n"
    )


def test_accept_all_breaks_with_break_that_has_single_quote_in_code(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: 'str')"))
    pyapi_yml_path = test_lib_path / ".." / PYAPI_YML_PATH
    assert not pyapi_yml_path.exists()
    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("another justification")

    assert pyapi_yml_path.read_text() == (
        "acceptedBreaks:\n"
        "  1.0.0:\n    test-pyapi-lib:\n    - code: 'ChangeParameterType: Change parameter type (test_pyapi_lib.functions.special_int_subtract): b: builtins.int => builtins.str'\n      justification: another justification\n"
        "versionOverrides: {}\n"
    )


def test_accept_all_breaks_no_breaks(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    app = PyAPIApplication(test_lib_path)

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    app.accept_all_breaks("why not")

    assert captured_output.getvalue() == "No Python API breaks found to accept.\n"

    sys.stdout = sys.__stdout__  # Reset stdout


def test_version_overrides_writes_overrides(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    app = PyAPIApplication(test_lib_path)
    pyapi_yml_path = test_lib_path / ".." / PYAPI_YML_PATH

    app.version_override("0.9.0")
    assert pyapi_yml_path.read_text() == "acceptedBreaks: {}\nversionOverrides:\n  1.0.0: 0.9.0\n"

    app.version_override("0.8.0")
    assert pyapi_yml_path.read_text() == "acceptedBreaks: {}\nversionOverrides:\n  1.0.0: 0.8.0\n"
