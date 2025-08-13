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

import math
import os
from dataclasses import asdict
from functools import cached_property
from pathlib import Path

import tomli
import yaml

from .aexpy_api_processor import AexpyAPIProcessor
from .api_processor import CannotFindAPIVersionError
from .color import ANSIColor
from .config import PyAPICheckerConfig
from .constants import (
    DOT_PALANTIR_DIR,
    PIP_INDEX_URL_ENV_VAR,
    PYAPI_CHECKER_CONFIG_KEY,
    PYAPI_YML_PATH,
    PYPI_INDEX_URL,
    PYPROJECT_TOML,
    UV_DEFAULT_INDEX_ENV_VAR,
)
from .git import get_git_version, get_previous_git_tag_from_HEAD, get_repo_root
from .model import AcceptedAPIBreak, PyAPIYml
from .utils import maybe_get_nested_value, print_with_local_color


class PyAPIApplication:
    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir
        self._pyproject_path = self._project_dir / PYPROJECT_TOML
        self._pyproject_toml = tomli.loads((self._pyproject_path).read_text())

        maybe_name = maybe_get_nested_value(["project", "name"], self._pyproject_toml)
        if not maybe_name:
            raise RuntimeError(f"Failed to find project.name in {self._pyproject_path}")
        if not isinstance(maybe_name, str):
            raise RuntimeError(f"project.name is not a string in {self._pyproject_path}")
        self._project_name: str = maybe_name

        self._config = PyAPICheckerConfig(**self._pyproject_toml.get("tool", {}).get(PYAPI_CHECKER_CONFIG_KEY, {}))
        self._index = (
            self._config.index
            or os.getenv(PIP_INDEX_URL_ENV_VAR)
            or os.getenv(UV_DEFAULT_INDEX_ENV_VAR)
            or PYPI_INDEX_URL
        )
        self._processor = AexpyAPIProcessor(self._project_dir, self._project_name, self._index, self._config.top_level_packages)
        self._pyapi_yml_path = self._repo_root / PYAPI_YML_PATH

    @cached_property
    def _repo_root(self) -> Path:
        return get_repo_root()

    @cached_property
    def _previous_version(self) -> str:
        previous_git_version = get_previous_git_tag_from_HEAD()
        return self._pyapi_yml_contents.versionOverrides.get(previous_git_version, previous_git_version)

    @cached_property
    def _pyapi_yml_contents(self) -> PyAPIYml:
        if not self._pyapi_yml_path.exists():
            return PyAPIYml({}, {})
        pyapi_yml = yaml.safe_load(self._pyapi_yml_path.read_text())
        if not isinstance(pyapi_yml, dict):
            raise RuntimeError(f"{self._pyapi_yml_path} is not valid yaml, cannot read to dict.")
        try:
            return PyAPIYml(**pyapi_yml)
        except Exception as e:
            raise RuntimeError(
                f"{self._pyapi_yml_path} does not have the valid structure for pyapi.yml files, cannot read to dict."
            ) from e

    @cached_property
    def _accepted_breaks_codes(self) -> set[str]:
        return set([b.code for b in self._get_accepted_breaks(self._previous_version)])

    @cached_property
    def _breaks(self) -> list[str]:
        try:
            return self._processor.check_api(self._previous_version)
        except CannotFindAPIVersionError as e:
            print(e)
            print_with_local_color(
                "If the above version was tagged but failed to publish, apply a version override via:", ANSIColor.RED
            )
            print_with_local_color("  pyapi versionOverride <last-published-version>", ANSIColor.CYAN)
            exit(1)

    def analyze(self) -> None:
        if get_git_version() == self._previous_version:
            print("Current version is the same as the previous version, this is a release version, skipping analysis.")
            return

        if not self._breaks:
            print("No Python API breaks found.")
            return

        unaccepted_breaks = []
        for api_break_code in self._breaks:
            if api_break_code not in self._accepted_breaks_codes:
                unaccepted_breaks.append(api_break_code)
        if not unaccepted_breaks:
            print("No unaccepted Python API breaks found.")
            return

        print_with_local_color(f"\nPython API breaks found in {self._project_name}:", ANSIColor.RED_UNDERLINED)
        for api_break_code in unaccepted_breaks:
            print_with_local_color(f"{api_break_code}", ANSIColor.RED_HIGH_INTENSITY)
        print("You can accept an API break via:")
        print_with_local_color(f'  pyapi acceptBreak "{self._breaks[0]}" ":justification:"', ANSIColor.CYAN)
        print("or all API breaks via:")
        print_with_local_color('  pyapi acceptAllBreaks ":justification:"', ANSIColor.CYAN)
        exit(1)

    def accept_break(self, code: str, justification: str) -> None:
        if code in self._accepted_breaks_codes:
            print(f"Break '{code}' is already accepted")
            return

        if not self._breaks or code not in self._breaks:
            print_with_local_color(
                f"\nBreak '{code}' is not a valid Python API break and cannot be accepted", ANSIColor.RED
            )
            exit(1)

        self._accept_breaks([AcceptedAPIBreak(code=code, justification=justification)])

    def accept_all_breaks(self, justification: str) -> None:
        if not self._breaks:
            print("No Python API breaks found to accept.")
            return

        breaks_to_accept = []
        for api_break_code in self._breaks:
            if api_break_code not in self._accepted_breaks_codes:
                breaks_to_accept.append(AcceptedAPIBreak(code=api_break_code, justification=justification))

        self._accept_breaks(breaks_to_accept)

    def version_override(self, replacement_version: str) -> None:
        modified_pyapi_yml = self._pyapi_yml_contents.union(
            PyAPIYml(acceptedBreaks={}, versionOverrides={self._previous_version: replacement_version})
        )
        self._write_modified_pyapi_yml(modified_pyapi_yml)

    def _accept_breaks(self, breaks_to_accept: list[AcceptedAPIBreak]) -> None:
        modified_pyapi_yml = self._pyapi_yml_contents.union(
            PyAPIYml(
                acceptedBreaks={self._previous_version: {self._project_name: breaks_to_accept}}, versionOverrides={}
            )
        )
        self._write_modified_pyapi_yml(modified_pyapi_yml)

    def _write_modified_pyapi_yml(self, modified_pyapi_yml: PyAPIYml) -> None:
        (self._repo_root / DOT_PALANTIR_DIR).mkdir(exist_ok=True)
        self._pyapi_yml_path.write_text(yaml.safe_dump(asdict(modified_pyapi_yml), width=math.inf))

    def _get_accepted_breaks(self, version: str) -> list[AcceptedAPIBreak]:
        return self._pyapi_yml_contents.enumerate_breaks(version, self._project_name)


class InvalidAPIBreakAcceptance(Exception):
    pass
