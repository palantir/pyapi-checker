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

from subprocess import CalledProcessError

import pytest

from pyapi.utils import run


def test_run_cli_missing_args() -> None:
    with pytest.raises(CalledProcessError) as e:
        run(["pyapi", "acceptBreak"])
    assert "Missing argument 'CODE'" in e.value.stderr.decode("utf-8")
    with pytest.raises(CalledProcessError) as e2:
        run(["pyapi", "acceptBreak", "code"])
    assert "Missing argument 'JUSTIFICATION'" in e2.value.stderr.decode("utf-8")
    with pytest.raises(CalledProcessError) as e3:
        run(["pyapi", "acceptAllBreaks"])
    assert "Missing argument 'JUSTIFICATION'" in e3.value.stderr.decode("utf-8")


def test_run_cli_help_message() -> None:
    help_message = run(["pyapi", "--help"])
    assert "Usage: pyapi [OPTIONS] COMMAND [ARGS]..." in help_message
    assert "analyze" in help_message
    assert "acceptBreak" in help_message
    assert "acceptAllBreaks" in help_message
