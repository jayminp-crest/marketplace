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

from typing import TYPE_CHECKING

import mp.core.file_utils
import mp.core.unix

if TYPE_CHECKING:
    import pathlib

    from mp.validate.validation_results import ValidationResults


def uv_lock_validation(
    integration_path: pathlib.Path, validation_results_obj: ValidationResults
) -> None:
    """Check if the 'uv.lock' file is consistent with 'pyproject.toml' file.

    Args:
        integration_path (pathlib.Path): Path to the integration directory.
        validation_results_obj (ValidationResults): Object to store validation outcomes.

    """
    validation_results_obj.errors.append("[yellow]Running uv lock validation [/yellow]")
    if not mp.core.file_utils.is_built(integration_path):
        mp.core.unix.check_lock_file(integration_path)
