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
from typing import TYPE_CHECKING, NotRequired, TypeAlias, TypedDict

import mp.core.file_utils
import mp.core.unix
from mp.core.constants import PROJECT_FILE, RELEASE_NOTES_FILE
from mp.core.exceptions import NonFatalValidationError
from mp.validate.utils import load_to_pyproject_toml_object, load_to_release_note_object

if TYPE_CHECKING:
    import pathlib

    from mp.core.data_models.pyproject_toml import PyProjectToml
    from mp.core.data_models.release_notes.metadata import ReleaseNote
    from mp.validate.validation_results import ValidationResults


class FileVersions(TypedDict):
    """Structure for holding old and new versions of a file."""

    old: NotRequired[PyProjectToml | ReleaseNote | None]
    new: NotRequired[PyProjectToml | ReleaseNote | None]


class TomlFileVersions(TypedDict):
    """Structure specifically for TOML file versions."""

    old: NotRequired[PyProjectToml | None]
    new: NotRequired[PyProjectToml | None]


class ReleaseNoteFileVersions(TypedDict):
    """Structure specifically for release note file versions."""

    old: NotRequired[ReleaseNote | None]
    new: NotRequired[list[ReleaseNote] | None]


class ExistingIntegrationFiles(TypedDict):
    """Structure for existing integration files with old and new versions."""

    toml: TomlFileVersions
    rn: ReleaseNoteFileVersions


class NewIntegrationFiles(TypedDict):
    """Structure for new integration files (only current versions)."""

    toml: NotRequired[PyProjectToml | None]
    rn: NotRequired[list[ReleaseNote] | None]


VersionBumpValidationData: TypeAlias = tuple[ExistingIntegrationFiles, NewIntegrationFiles]


REQUIRED_CHANGED_FILES_NUM: int = 2


def version_bump_validation(
    integration_path: pathlib.Path, validation_results_obj: ValidationResults
) -> None:
    """Validate that `project.toml` and `release_notes.yml` files are correctly versioned.

    Args:
        integration_path (pathlib.Path): Path to the integration directory.
        validation_results_obj (ValidationResults): Object to store validation outcomes.

    Raises:
        NonFatalValidationError: If versioning rules are violated.

    """
    validation_results_obj.errors.append("[yellow]Running version bump validation [/yellow]")

    head_sha: str | None = os.environ.get("GITHUB_SHA")
    if not head_sha:
        return

    changed_files: list[pathlib.Path] = mp.core.unix.get_files_unmerged_to_main_branch(
        "main", head_sha, integration_path
    )
    if not changed_files:
        return

    relevant_files: list[pathlib.Path] = [
        p for p in changed_files if p.name in {PROJECT_FILE, RELEASE_NOTES_FILE}
    ]
    if not relevant_files or len(relevant_files) != REQUIRED_CHANGED_FILES_NUM:
        msg: str = "project.toml and release_notes.yml files must be updated before PR"
        raise NonFatalValidationError(msg)

    existing_files, new_files = _create_data_for_version_bump_validation(relevant_files)
    _version_bump_validation_run_checks(existing_files, new_files)


def _create_data_for_version_bump_validation(
    relevant_files: list[pathlib.Path],
) -> VersionBumpValidationData:
    existing_files: ExistingIntegrationFiles = {
        "toml": TomlFileVersions(),
        "rn": ReleaseNoteFileVersions(),
    }
    new_files: NewIntegrationFiles = NewIntegrationFiles()

    pyproject_path = next(p for p in relevant_files if p.name == PROJECT_FILE)
    rn_path = next(p for p in relevant_files if p.name == RELEASE_NOTES_FILE)

    try:
        old_toml_content = mp.core.unix.get_file_content_from_main_branch(pyproject_path)
        existing_files["toml"]["old"] = load_to_pyproject_toml_object(old_toml_content)
        existing_files["toml"]["new"] = load_to_pyproject_toml_object(pyproject_path.read_text())

        old_rn_content = mp.core.unix.get_file_content_from_main_branch(rn_path)
        existing_files["rn"]["old"] = _get_last_note(old_rn_content)
        existing_files["rn"]["new"] = _get_new_rn_notes(rn_path.read_text(), old_rn_content)

    except mp.core.unix.NonFatalCommandError:
        new_files["toml"] = load_to_pyproject_toml_object(pyproject_path.read_text())
        new_files["rn"] = load_to_release_note_object(rn_path.read_text())

    return existing_files, new_files


def _get_last_note(content: str) -> ReleaseNote | None:
    notes = load_to_release_note_object(content)
    return notes[-1] if notes else None


def _get_new_rn_notes(new_rn_content: str, old_rn_content: str) -> list[ReleaseNote]:
    new_notes: list[ReleaseNote] = load_to_release_note_object(new_rn_content)
    old_notes: list[ReleaseNote] = load_to_release_note_object(old_rn_content)
    return new_notes[len(old_notes):]


def _version_bump_validation_run_checks(
    existing_files: ExistingIntegrationFiles, new_files: NewIntegrationFiles
) -> None:
    msg: str
    if existing_files["toml"].get("new") and existing_files["toml"].get("old"):
        toml_new_version = existing_files["toml"].get("new").project.version
        toml_old_version = existing_files["toml"].get("old").project.version

        if toml_new_version != toml_old_version + 1.0:
            msg = "The project.toml Version must be incremented by exactly 1.0."
            raise NonFatalValidationError(msg)

        new_notes: list[ReleaseNote] = existing_files["rn"].get("new")
        msg = "The release note's version must match the new version of the project.toml."
        if not _rn_is_valid(new_notes, toml_new_version):
            raise NonFatalValidationError(msg)

    elif new_files.get("toml") and new_files.get("rn"):
        toml_version = new_files["toml"].project.version
        new_notes: list[ReleaseNote] = new_files["rn"]
        msg = (
            "New integration project.toml and release_note.yaml version must be initialize to 1.0."
        )
        if toml_version != 1.0 or not _rn_is_valid(new_notes):
            raise NonFatalValidationError(msg)

    else:
        msg = "New integration missing project.toml and/or release_note.yaml."
        raise NonFatalValidationError(msg)


def _rn_is_valid(new_notes: list[ReleaseNote], version_to_compare: float = 1.0) -> bool:
    if not new_notes:
        return False
    return all(new_note.version == version_to_compare for new_note in new_notes)
