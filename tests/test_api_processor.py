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

from pathlib import Path
from unittest.mock import MagicMock

from pyapi.aexpy_api_processor import AexpyAPIProcessor
from pyapi.api_processor import APIProcessor
from pyapi.constants import PYPI_INDEX_URL


def test_check_api_multiple_times_with_no_changes(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    processor: APIProcessor = AexpyAPIProcessor(test_lib_path, "test-pyapi-lib", PYPI_INDEX_URL)
    assert processor.check_api("1.0.0") == []
    assert processor.check_api("1.0.0") == []


def test_check_api_multiple_times_with_local_changes(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    processor: APIProcessor = AexpyAPIProcessor(test_lib_path, "test-pyapi-lib", PYPI_INDEX_URL)
    assert processor.check_api("1.0.0") == []

    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: str, b: str)", "(b: str, a: str)"))

    assert set(processor.check_api("1.0.0")) == {
        "MoveParameter: Move parameter (test_pyapi_lib.functions.special_string_add): b: 2 -> 1.",
        "MoveParameter: Move parameter (test_pyapi_lib.functions.special_string_add): a: 1 -> 2.",
    }


def test_check_api_non_breaking_change(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    processor: APIProcessor = AexpyAPIProcessor(test_lib_path, "test-pyapi-lib", PYPI_INDEX_URL)
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(
        functions_path.read_text().replace("(a: str, b: str)", '(a: str, b: str, c: str = "foo")')
    )

    assert processor.check_api("1.0.0") == []


def test_check_api_breaking_and_non_breaking_change(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    processor: APIProcessor = AexpyAPIProcessor(test_lib_path, "test-pyapi-lib", PYPI_INDEX_URL)
    functions_path = test_lib_path / "test_pyapi_lib/functions.py"
    functions_path.write_text(
        functions_path.read_text().replace("(a: str, b: str)", '(b: str, a: str, c: str = "foo")')
    )

    assert set(processor.check_api("1.0.0")) == {
        "MoveParameter: Move parameter (test_pyapi_lib.functions.special_string_add): b: 2 -> 1.",
        "MoveParameter: Move parameter (test_pyapi_lib.functions.special_string_add): a: 1 -> 2.",
    }


def test_check_api_public_member_of_test_package_does_not_cause_break(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, mock_run = test_lib
    processor: APIProcessor = AexpyAPIProcessor(test_lib_path, "test-pyapi-lib", PYPI_INDEX_URL)
    output_path = test_lib_path / "test_pyapi_lib/_output.py"
    output_path.write_text(
        output_path.read_text().replace("def __init__(self) -> None:", "def __init__(self, description: str) -> None:")
    )

    # This technically wouldn't be a break even if we analyzed the "tests" package with the current
    # source because the tests package wouldn't exist in the wheel so "OutputHandler" would be considered
    # private in the wheel and thus doesn't matter if it's public and/or modified in the source.
    # But check this anyway for redundancy.
    assert set(processor.check_api("1.0.0")) == set()

    # Check we're indeed passing the package name to aexpy.
    assert any(
        [
            "python3",
            "-m",
            "aexpy",
            "preprocess",
            "-s",
            str(test_lib_path),
            str(test_lib_path / "build/pyapi/preprocessed-test-pyapi-lib-source.json"),
            "-m",
            "test_pyapi_lib",
        ]
        == call[1]["args"]
        for call in mock_run.call_args_list
    )


def test_check_api_public_member_of_main_package_does_cause_break(test_lib: tuple[Path, MagicMock]) -> None:
    test_lib_path, _ = test_lib
    processor: APIProcessor = AexpyAPIProcessor(test_lib_path, "test-pyapi-lib", PYPI_INDEX_URL)
    output_path = test_lib_path / "test_pyapi_lib/_output.py"
    output_path.write_text(output_path.read_text().replace("def foo() -> str:", "def foo() -> bool:"))

    assert set(processor.check_api("1.0.0")) == {
        "ChangeReturnType: Change return type (test_pyapi_lib._output.Utils.foo): builtins.str => builtins.bool"
    }
