# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, cast

import toml
import yaml

from mp.core.data_models.pyproject_toml import PyProjectToml, PyProjectTomlFile
from mp.core.data_models.release_notes.metadata import NonBuiltReleaseNote, ReleaseNote

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable


class Configurations(NamedTuple):
    only_pre_build: bool


def get_marketplace_paths_from_names(
    names: Iterable[str],
    marketplace_path: pathlib.Path,
) -> set[pathlib.Path]:
    """Retrieve existing marketplace paths from a list of names.

    Args:
        names: An iterable of names, where each name can be a string
            representing a file/directory name of integration or group.
        marketplace_path: The base `pathlib.Path` object representing the
            root directory of the marketplace.

    Returns:
        A `set` of `pathlib.Path` objects representing the paths that
        were found to exist within the `marketplace_path`.

    """
    result: set[pathlib.Path] = set()
    for n in names:
        if (p := marketplace_path / n).exists():
            result.add(p)
    return result


def load_to_release_note_object(text: str) -> list[ReleaseNote]:
    """Load a release note string to an ReleaseNote object.

    Args:
        text: the text to load.

    Returns:
        a list of `ReleaseNote` objects.

    """
    rn_data: list[dict] = yaml.safe_load(text)
    if not rn_data:
        return []
    return [
        ReleaseNote._from_non_built(cast("NonBuiltReleaseNote", data))  # noqa: SLF001
        for data in rn_data
    ]


def load_to_pyproject_toml_object(text: str) -> PyProjectToml:
    """Load a toml string into a PyProjectToml object.

    Args:
        text: the string to parse into a PyProjectToml object.

    Returns:
        a `PyProjectToml` object.

    """
    pyproject_data: PyProjectTomlFile = cast("PyProjectTomlFile", toml.loads(text))
    return PyProjectToml.model_load(pyproject_data)
