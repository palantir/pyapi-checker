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

import typer

from .app import PyAPIApplication

app = typer.Typer()
pyapi_app = PyAPIApplication(Path.cwd().absolute())


@app.command()
def analyze() -> None:
    pyapi_app.analyze()


@app.command(name="acceptBreak")
def accept_break(
    code: str,
    justification: str,
) -> None:
    pyapi_app.accept_break(code, justification)


@app.command(name="acceptAllBreaks")
def accept_all_breaks(justification: str) -> None:
    pyapi_app.accept_all_breaks(justification)


@app.command(name="versionOverride")
def version_override(replacement_version: str) -> None:
    pyapi_app.version_override(replacement_version)


if __name__ == "__main__":
    app()
