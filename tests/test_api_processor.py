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

from pyapi.aexpy_api_processor import AexpyAPIProcessor
from pyapi.api_processor import APIProcessor
from pyapi.constants import PYPI_INDEX_URL


def test_check_api_multiple_times_with_no_changes(test_lib: Path) -> None:
    processor: APIProcessor = AexpyAPIProcessor(test_lib, "test-pyapi-lib", PYPI_INDEX_URL)
    assert processor.check_api("1.0.0") == []
    assert processor.check_api("1.0.0") == []


def test_check_api_multiple_times_with_local_changes(test_lib: Path) -> None:
    processor: APIProcessor = AexpyAPIProcessor(test_lib, "test-pyapi-lib", PYPI_INDEX_URL)
    assert processor.check_api("1.0.0") == []

    functions_path = test_lib / "test_pyapi_lib/functions.py"
    functions_path.write_text(functions_path.read_text().replace("(a: str, b: str)", "(b: str, a: str)"))

    assert set(processor.check_api("1.0.0")) == {
        "MoveParameter: Move parameter (test_pyapi_lib.functions.special_string_add): b: 2 -> 1.",
        "MoveParameter: Move parameter (test_pyapi_lib.functions.special_string_add): a: 1 -> 2.",
    }


def test_check_api_non_breaking_change(test_lib: Path) -> None:
    processor: APIProcessor = AexpyAPIProcessor(test_lib, "test-pyapi-lib", PYPI_INDEX_URL)
    functions_path = test_lib / "test_pyapi_lib/functions.py"
    functions_path.write_text(
        functions_path.read_text().replace("(a: str, b: str)", '(a: str, b: str, c: str = "foo")')
    )

    assert processor.check_api("1.0.0") == []


def test_check_api_breaking_and_non_breaking_change(test_lib: Path) -> None:
    processor: APIProcessor = AexpyAPIProcessor(test_lib, "test-pyapi-lib", PYPI_INDEX_URL)
    functions_path = test_lib / "test_pyapi_lib/functions.py"
    functions_path.write_text(
        functions_path.read_text().replace("(a: str, b: str)", '(b: str, a: str, c: str = "foo")')
    )

    assert set(processor.check_api("1.0.0")) == {
        "MoveParameter: Move parameter (test_pyapi_lib.functions.special_string_add): b: 2 -> 1.",
        "MoveParameter: Move parameter (test_pyapi_lib.functions.special_string_add): a: 1 -> 2.",
    }
