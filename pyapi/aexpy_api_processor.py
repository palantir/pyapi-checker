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
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any

from aexpy.models.difference import BreakingRank

from .api_processor import APIProcessor, CannotFindAPIVersionError
from .constants import PYAPI_BUILD_DIR
from .utils import run


class AexpyAPIProcessor(APIProcessor):
    def __init__(self, project_path: Path, project_name: str, python_index: str):
        self._project_path = project_path
        self._python_index = python_index
        self._build_dir = self._project_path / PYAPI_BUILD_DIR
        self._project_name = project_name

    def check_api(self, previous_version: str) -> list[str]:
        wheel = self._download_wheel(self._project_path.name, previous_version)
        preprocessed_output = self._preprocess()
        extracted1 = self._extract_from_wheel(wheel, previous_version)
        extracted2 = self._extract_from_preprocessed(preprocessed_output)
        diff_output = self._diff(extracted1, extracted2, previous_version)
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

    def _preprocess(self) -> Path:
        preprocessed_output = self._build_dir / f"preprocessed-{self._project_path.name}-source.json"
        self._run_aexpy(["preprocess", "-s", str(self._project_path), str(preprocessed_output)])
        return preprocessed_output

    def _extract_from_preprocessed(self, preprocessed_output: Path) -> Path:
        extracted_output = self._build_dir / f"extracted-{self._project_path.name}-source.json"
        self._run_aexpy(["extract", str(preprocessed_output), str(extracted_output)])
        return extracted_output

    def _extract_from_wheel(self, distribution: Path, version: str) -> Path:
        extracted_output = self._build_dir / f"extracted-{self._project_path.name}-{version}.json"
        if extracted_output.exists():
            return extracted_output
        # Remove previous extracted json files from wheels.
        for file in self._build_dir.glob(f"extracted-{self._project_path.name}-*.*.*.json"):
            file.unlink()
        self._run_aexpy(["extract", "-w", str(distribution), str(extracted_output)])
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
