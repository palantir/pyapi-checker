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

import os
import subprocess
from typing import Any

from .color import ANSIColor


def maybe_get_nested_value(keys: list[str], d: dict[str, Any]) -> Any | None:
    if len(keys) == 1:
        return d.get(keys[0])
    sub_dict = d.get(keys[0])
    if sub_dict:
        keys.pop(0)
        return maybe_get_nested_value(keys, sub_dict)
    return None


def run(args: list[str]) -> str:
    try:
        res = subprocess.run(args=args, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(e.stdout.decode("utf-8"))
        print(e.stderr.decode("utf-8"))
        raise e
    return res.stdout.decode("utf-8")


def merge_dicts(dict1: dict[Any, Any], dict2: dict[Any, Any], root_key: str | None = None) -> dict[Any, Any]:
    """
    Merges dictionaries together recursively where key, value pairs in dict2 override key, value
    pairs in dict1 if the keys are the same unless 1) the values are dictionaries and then these
    dictionaries are merged recursively with the same rules or 2) the values are lists in which
    case the list from dict2 is appended to dict1. Returns merged dictionary.
    """
    for key, value in dict2.items():
        full_key_name = root_key + "." + key if root_key else key
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            dict1[key] = merge_dicts(dict1[key], value, full_key_name)
        elif key in dict1 and isinstance(dict1[key], list) and isinstance(value, list):
            dict1[key] = dict1[key] + value
        else:
            dict1[key] = value
    return dict1


def print_with_local_color(message: str, color: ANSIColor) -> None:
    if os.getenv("CI"):
        print(message)
        return
    print(f"{color.value}{message}{ANSIColor.NO_COLOR.value}")
