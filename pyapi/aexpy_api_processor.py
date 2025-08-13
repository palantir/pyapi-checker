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

import json
from enum import Enum
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any

from aexpy.models.difference import BreakingRank

from .api_processor import APIProcessor, CannotFindAPIVersionError
from .constants import PYAPI_BUILD_DIR
from .utils import run

SOURCE_VERSION_STR = "source"


class PreprocessMode(Enum):
    WHEEL = "-w"
    SOURCE = "-s"


class AexpyAPIProcessor(APIProcessor):
    def __init__(self, project_path: Path, project_name: str, python_index: str, top_level_packages: list[str] | None):
        self._project_path = project_path
        self._python_index = python_index
        self._top_level_packages = top_level_packages
        self._build_dir = self._project_path / PYAPI_BUILD_DIR
        self._project_name = project_name

    def check_api(self, previous_version: str) -> list[str]:
        wheel = self._download_wheel(self._project_path.name, previous_version)
        preprocessed_wheel = self._preprocess_wheel(wheel, previous_version)
        preprocessed_source = self._preprocess_source()
        extracted_wheel = self._extract_from_preprocessed_wheel(preprocessed_wheel, previous_version)
        extracted_source = self._extract_from_preprocessed_source(preprocessed_source)
        diff_output = self._diff(extracted_wheel, extracted_source, previous_version)
        return self._parse_diff(diff_output)

    def _download_wheel(self, package_name: str, version: str) -> Path:
        download_dir = self._build_dir / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        wheel_glob_pattern = f"{self._project_name.replace('-', '_')}-{version}*.whl"
        present_wheels = list(download_dir.glob(wheel_glob_pattern))
        if len(present_wheels) == 1:
            return present_wheels[0]
        elif len(present_wheels) > 1:
            raise RuntimeError(f"Multiple wheels found before download for {package_name} {version} in {download_dir}.")
        # If not found delete any previously downloaded wheels.
        for dist in download_dir.glob("*"):
            dist.unlink()
        try:
            self._run_python_module(
                [
                    "pip",
                    "download",
                    f"{self._project_name}=={version}",
                    "--index-url",
                    self._python_index,
                    "--no-deps",
                    "--only-binary=:all:",
                    "-d",
                    str(download_dir),
                ]
            )
        except CalledProcessError as e:
            if "Could not find a version that satisfies the requirement" in e.stderr.decode("utf-8"):
                raise CannotFindAPIVersionError(f"Cannot find {package_name} {version} in Python index.", e)
            raise e
        present_wheels = list(download_dir.glob(wheel_glob_pattern))
        if len(present_wheels) == 1:
            return present_wheels[0]
        elif len(present_wheels) > 1:
            raise RuntimeError(f"Multiple wheels found after download for {package_name} {version} in {download_dir}.")
        raise CannotFindAPIVersionError(f"Failed to download {package_name} {version} from Python index.")

    def _preprocess_wheel(self, distribution: Path, version: str) -> Path:
        return self._preprocess(PreprocessMode.WHEEL, distribution, version)

    def _preprocess_source(self) -> Path:
        return self._preprocess(PreprocessMode.SOURCE, self._project_path, SOURCE_VERSION_STR)

    def _preprocess(self, mode: PreprocessMode, input: Path, version_str: str) -> Path:
        preprocessed_output = self._build_dir / f"preprocessed-{self._project_path.name}-{version_str}.json"
        command = ["preprocess", mode.value, str(input), str(preprocessed_output)]
        if self._top_level_packages:
            command.extend([f"-m={package}" for package in self._top_level_packages])
        self._run_aexpy(command)
        return preprocessed_output

    def _extract_from_preprocessed_source(self, preprocessed_output: Path) -> Path:
        return self._extract_from_preprocessed(preprocessed_output, SOURCE_VERSION_STR)

    def _extract_from_preprocessed_wheel(self, preprocessed_output: Path, version: str) -> Path:
        return self._extract_from_preprocessed(
            preprocessed_output, version, f"extracted-{self._project_path.name}-*.*.*.json"
        )

    # Passing a file_cleanup_glob means that the output is cached and thus if already exists is used
    # and not recomputed and otherwise all files matching the glob are removed and then the output is
    # recomputed. Not passing it means no caching or cleanup and output is always recomputed.
    def _extract_from_preprocessed(
        self, preprocessed_output: Path, version_str: str, file_cleanup_glob: str | None = None
    ) -> Path:
        extracted_output = self._build_dir / f"extracted-{self._project_path.name}-{version_str}.json"
        if file_cleanup_glob:
            if extracted_output.exists():
                return extracted_output
            # Remove previous extracted json files from wheels.
            for file in self._build_dir.glob(file_cleanup_glob):
                file.unlink()
        self._run_aexpy(["extract", str(preprocessed_output), str(extracted_output)])
        return extracted_output

    def _diff(self, extracted1: Path, extracted2: Path, version: str) -> Path:
        diff_output = self._build_dir / f"diff-{self._project_path.name}-{version}.json"
        # TODO(BenjaminLowry): hash source files so we can use old preprocessed and diff files for efficiency.
        # Remove previous diff json files.
        for file in self._build_dir.glob(f"diff-{self._project_path.name}-*.*.*.json"):
            file.unlink()
        self._run_aexpy(["diff", str(extracted1), str(extracted2), str(diff_output)])
        return diff_output

    def _parse_diff(self, diff_output: Path) -> list[str]:
        diff_json: dict[str, Any] = json.loads(diff_output.read_text())
        maybe_entries = diff_json.get("entries")
        if maybe_entries is None:
            raise RuntimeError(f"Failed to parse diff output: cannot find 'entries' field in {diff_output}")
        api_breaks = []
        for entry in maybe_entries.values():
            maybe_rank = entry.get("rank")
            if maybe_rank is None:
                raise RuntimeError(f"Failed to parse diff output: cannot find 'rank' field in {diff_output}")
            if maybe_rank != BreakingRank.High.value and maybe_rank != BreakingRank.Medium.value:
                continue

            maybe_kind = entry.get("kind")
            if not maybe_kind:
                raise RuntimeError(f"Failed to parse diff output: cannot find 'kind' field in {diff_output}")
            maybe_message = entry.get("message")
            if not maybe_message:
                raise RuntimeError(f"Failed to parse diff output: cannot find 'message' field in {diff_output}")
            api_breaks.append(f"{maybe_kind}: {maybe_message}")
        return api_breaks

    def _run_aexpy(self, args: list[str]) -> None:
        self._run_python_module(["aexpy"] + args)

    def _run_python_module(self, args: list[str]) -> None:
        run(["python3", "-m"] + args)
