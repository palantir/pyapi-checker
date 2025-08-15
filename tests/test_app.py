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
from textwrap import dedent
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
    assert captured_output.getvalue() == dedent(f"""\
    {ANSIColor.RED_UNDERLINED.value}
    Python API breaks found in test-pyapi-lib:{ANSIColor.NO_COLOR.value}
    {ANSIColor.RED_HIGH_INTENSITY.value}AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.{ANSIColor.NO_COLOR.value}
    You can accept an API break via:
    {ANSIColor.CYAN.value}  pyapi acceptBreak "AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c." ":justification:"{ANSIColor.NO_COLOR.value}
    or all API breaks via:
    {ANSIColor.CYAN.value}  pyapi acceptAllBreaks ":justification:"{ANSIColor.NO_COLOR.value}
    """)

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
    assert captured_output.getvalue() == dedent("""
    Python API breaks found in test-pyapi-lib:
    RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False.
    RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): meow
    RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.
    ChangeParameterType: Change parameter type (test_pyapi_lib.functions.special_string_add): a: builtins.str => builtins.int
    You can accept an API break via:
      pyapi acceptBreak "RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False." ":justification:"
    or all API breaks via:
      pyapi acceptAllBreaks ":justification:"
    """)

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
    pyapi_yml_file.write_text(
        dedent("""
    acceptedBreaks: {}
    versionOverrides:
      1.0.0: 0.9.0
    """)
    )

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

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      1.0.0:
        test-pyapi-lib:
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: basic justification
    versionOverrides: {}
    """)


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

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      1.0.0:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): meow'
          justification: meow is never used
    versionOverrides: {}
    """)

    captured_output = StringIO()
    sys.stdout = captured_output  # Redirect stdout.

    app = PyAPIApplication(test_lib_path)  # Recreate app for new command.
    with pytest.raises(SystemExit) as cm:
        app.analyze()

    assert cm.value.code == 1
    assert captured_output.getvalue() == dedent("""
    Python API breaks found in test-pyapi-lib:
    RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False.
    RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.
    ChangeParameterType: Change parameter type (test_pyapi_lib.functions.special_string_add): a: builtins.str => builtins.int
    You can accept an API break via:
      pyapi acceptBreak "RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False." ":justification:"
    or all API breaks via:
      pyapi acceptAllBreaks ":justification:"
    """)

    sys.stdout = sys.__stdout__  # Reset stdout


def test_accept_break_that_is_already_accepted(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_text = dedent("""\
    acceptedBreaks:
      1.0.0:
        test-pyapi-lib:
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: previous acceptance
    versionOverrides: {}
    """)
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

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      1.0.0:
        test-pyapi-lib:
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: basic justification
    versionOverrides: {}
    """)


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

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      1.0.0:
        test-pyapi-lib:
        - code: 'RemoveParameterDefault: Switch parameter optional (test_pyapi_lib.animals.Animal.__init__): is_mammal: True -> False.'
          justification: these are all irrelevant
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): meow'
          justification: these are all irrelevant
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: these are all irrelevant
        - code: 'ChangeParameterType: Change parameter type (test_pyapi_lib.functions.special_string_add): a: builtins.str => builtins.int'
          justification: these are all irrelevant
    versionOverrides: {}
    """)


def test_accept_all_breaks_with_break_and_existing_accepted(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_path.write_text(
        dedent("""\
    acceptedBreaks:
      0.191.0:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      1.0.0:
        test-pyapi-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
    versionOverrides: {}
    """)
    )
    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("basic justification")

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      0.191.0:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      1.0.0:
        test-pyapi-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: basic justification
    versionOverrides: {}
    """)


def test_accept_all_breaks_with_break_and_older_and_newer_existing_accepted(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_path.write_text(
        dedent("""\
    acceptedBreaks:
      0.9.0:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      1.1.0:
        test-pyapi-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
    versionOverrides: {}
    """)
    )

    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("basic justification")

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      0.9.0:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      1.0.0:
        test-pyapi-lib:
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: basic justification
      1.1.0:
        test-pyapi-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
    versionOverrides: {}
    """)


def test_accept_all_breaks_with_break_and_newer_existing_accepted(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_path.write_text(
        dedent("""\
    acceptedBreaks:
      1.0.1:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      5.302.0:
        test-pyapi-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
    versionOverrides: {}
    """)
    )

    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("basic justification")

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      1.0.0:
        test-pyapi-lib:
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: basic justification
      1.0.1:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      5.302.0:
        test-pyapi-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
    versionOverrides: {}
    """)


def test_accept_all_breaks_with_break_and_older_existing_accepted(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_path.write_text(
        dedent("""\
    acceptedBreaks:
      0.1.0:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      0.999.999:
        test-pyapi-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
    versionOverrides: {}
    """)
    )

    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("basic justification")

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      0.1.0:
        test-pyapi-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      0.999.999:
        test-pyapi-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
      1.0.0:
        test-pyapi-lib:
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: basic justification
    versionOverrides: {}
    """)


def test_accept_all_breaks_with_break_and_other_projects_for_same_version(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_path.write_text(
        dedent("""\
    acceptedBreaks:
      1.0.0:
        other-test-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
        very-cool-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
    versionOverrides: {}
    """)
    )

    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("basic justification")

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      1.0.0:
        other-test-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
        test-pyapi-lib:
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: basic justification
        very-cool-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
    versionOverrides: {}
    """)


def test_accept_all_breaks_with_break_and_other_projects_on_different_version(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: int, c: int)"))
    palantir_path = test_lib_path / ".." / ".palantir"
    palantir_path.mkdir(parents=True)
    pyapi_yml_path = palantir_path / PYAPI_YML_FILENAME
    pyapi_yml_path.write_text(
        dedent("""\
    acceptedBreaks:
      0.9.0:
        other-test-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
        very-cool-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
    versionOverrides: {}
    """)
    )

    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("basic justification")

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      0.9.0:
        other-test-lib:
        - code: 'RemoveRequiredParameter: Remove PositionalOrKeyword parameter (test_pyapi_lib.functions.special_string_add): b.'
          justification: previous acceptance
        very-cool-lib:
        - code: 'RemoveMethod: Remove method (test_pyapi_lib.animals.Cat): purr'
          justification: no purrs allowed
      1.0.0:
        test-pyapi-lib:
        - code: 'AddRequiredParameter: Add PositionalOrKeyword parameter (test_pyapi_lib.functions.special_int_subtract): c.'
          justification: basic justification
    versionOverrides: {}
    """)


def test_accept_all_breaks_with_break_that_has_single_quote_in_code(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: int, b: int)", "(a: int, b: 'str')"))
    pyapi_yml_path = test_lib_path / ".." / PYAPI_YML_PATH
    assert not pyapi_yml_path.exists()
    app = PyAPIApplication(test_lib_path)

    app.accept_all_breaks("another justification")

    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks:
      1.0.0:
        test-pyapi-lib:
        - code: 'ChangeParameterType: Change parameter type (test_pyapi_lib.functions.special_int_subtract): b: builtins.int => builtins.str'
          justification: another justification
    versionOverrides: {}
    """)


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
    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks: {}
    versionOverrides:
      1.0.0: 0.9.0
    """)

    app.version_override("0.8.0")
    assert pyapi_yml_path.read_text() == dedent("""\
    acceptedBreaks: {}
    versionOverrides:
      1.0.0: 0.8.0
    """)
