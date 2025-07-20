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

import os
from typing import TYPE_CHECKING

import rich
import typer

import mp.core.file_utils
import mp.core.unix
from mp.core.exceptions import FatalValidationError, NonFatalValidationError

from .utils import load_to_pyproject_toml_object, load_to_release_note_object
from .validation_results import ValidationResults, ValidationTypes

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable

    from mp.core.data_models.pyproject_toml import PyProjectToml
    from mp.core.data_models.release_notes.metadata import ReleaseNote


REQUIRED_CHANGED_FILES_NUM: int = 2
ERROR_MSG: str = "{0}"


class PreBuildValidations:
    def __init__(self, integration_path: pathlib.Path) -> None:
        self.integration_path: pathlib.Path = integration_path
        self.results: ValidationResults = ValidationResults(
            integration_path.name, ValidationTypes.PRE_BUILD
        )

    def run_pre_build_validation(self) -> None:
        """Run all the pre-build validations.

        Raises:
            typer.Exit: If a `FatalValidationError` is encountered during any
                of the validation checks.

        """
        self.results.errors.append(
            "[bold green]Running pre build validation on "
            f"---- {self.integration_path.name} ---- \n[/bold green]"
        )

        for func in self._get_validation_functions():
            try:
                func()
            except NonFatalValidationError as e:
                self.results.errors.append(f"[red]{e}\n[/red]")

            except FatalValidationError as error:
                rich.print(f"[bold red]{error}[/bold red]")
                raise typer.Exit(code=1) from error

        self.results.errors.append(
            "[bold green]Completed pre build validation on "
            f"---- {self.integration_path.name} ---- \n[/bold green]"
        )

        self.results.is_success = len(self.results.errors) == (
            len(self._get_validation_functions()) + 2
        )

    def _get_validation_functions(self) -> list[Callable]:
        return [self._uv_lock_validation, self._version_bump_validation]

    def _uv_lock_validation(self) -> None:
        self.results.errors.append("[yellow]Running uv lock validation [/yellow]")
        if not mp.core.file_utils.is_built(self.integration_path):
            mp.core.unix.check_lock_file(self.integration_path)

    def _version_bump_validation(self) -> None:
        self.results.errors.append("[yellow]Running version bump validation [/yellow]")

        head_sha = os.environ.get("GITHUB_SHA")
        if not head_sha:
            return

        changed_files: list[pathlib.Path] = mp.core.unix.get_changed_files_from_main(
            "main", head_sha, self.integration_path
        )
        if not changed_files:
            return

        relevant_files: list[pathlib.Path] = [
            p for p in changed_files if p.name in {"pyproject.toml", "release_notes.yaml"}
        ]
        if not relevant_files or len(relevant_files) != REQUIRED_CHANGED_FILES_NUM:
            raise NonFatalValidationError(
                ERROR_MSG.format(
                    "project.toml and release_notes.yml files must be updated before PR"
                )
            )

        existing_files, new_files = PreBuildValidations._create_data_for_version_bump_validation(
            relevant_files
        )
        PreBuildValidations._version_bump_validation_run_checks(existing_files, new_files)

    @staticmethod
    def _create_data_for_version_bump_validation(
        relevant_files: list[pathlib.Path],
    ) -> tuple[dict, dict]:
        existing_files: dict[str, dict[str, PyProjectToml | ReleaseNote | None]] = {
            "toml": {},
            "rn": {},
        }
        new_files: dict[str, PyProjectToml | ReleaseNote | None] = {}

        pyproject_path = next(p for p in relevant_files if p.name == "pyproject.toml")
        rn_path = next(p for p in relevant_files if p.name == "release_notes.yaml")

        def get_last_note(content: str) -> ReleaseNote | None:
            notes = load_to_release_note_object(content)
            return notes[-1] if notes else None

        try:
            existing_files["toml"]["new"] = load_to_pyproject_toml_object(
                pyproject_path.read_text()
            )
            old_toml_content = mp.core.unix.get_file_content_from_main(pyproject_path)
            existing_files["toml"]["old"] = load_to_pyproject_toml_object(old_toml_content)

            existing_files["rn"]["new"] = get_last_note(rn_path.read_text())
            old_rn_content = mp.core.unix.get_file_content_from_main(rn_path)
            existing_files["rn"]["old"] = get_last_note(old_rn_content)

        except mp.core.unix.NonFatalCommandError:
            new_files["toml"] = load_to_pyproject_toml_object(pyproject_path.read_text())
            new_files["rn"] = get_last_note(rn_path.read_text())

        return existing_files, new_files

    @staticmethod
    def _version_bump_validation_run_checks(existing_files: dict, new_files: dict) -> None:
        if existing_files.get("toml") and existing_files.get("rn"):
            toml_new_version = existing_files["toml"]["new"].project.version
            toml_old_version = existing_files["toml"]["old"].project.version
            if toml_new_version != toml_old_version + 1.0:
                raise NonFatalValidationError(
                    ERROR_MSG.format("The project.toml Version must be incremented by exactly 1.0.")
                )
            new_rn = existing_files["rn"].get("new")
            if not new_rn or new_rn.version != toml_new_version:
                raise NonFatalValidationError(
                    ERROR_MSG.format(
                        "The release note's version must match the new version of the project.toml."
                    )
                )

        elif new_files.get("toml") and new_files.get("rn"):
            toml_version = new_files["toml"].project.version
            rn_version = new_files["rn"].project.version
            if toml_version != rn_version != 1.0:
                raise NonFatalValidationError(
                    ERROR_MSG.format(
                        "New integration project.toml and release_note.yaml version "
                        "must be initialize to 1.0."
                    )
                )

        else:
            raise NonFatalValidationError(
                ERROR_MSG.format("New integration missing project.toml and/or release_note.yaml.")
            )
