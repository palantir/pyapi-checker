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

from pydantic.dataclasses import dataclass

from .utils import merge_dicts


@dataclass
class AcceptedAPIBreak:
    code: str
    justification: str


@dataclass
class PyAPIYml:
    acceptedBreaks: dict[str, dict[str, list[AcceptedAPIBreak]]]
    versionOverrides: dict[str, str]

    def union(self, other: "PyAPIYml") -> "PyAPIYml":
        return PyAPIYml(
            merge_dicts(self.acceptedBreaks, other.acceptedBreaks),
            merge_dicts(self.versionOverrides, other.versionOverrides),
        )

    def enumerate_breaks(self, version: str, project_name: str) -> list[AcceptedAPIBreak]:
        return self.acceptedBreaks.get(version, {}).get(project_name, [])
