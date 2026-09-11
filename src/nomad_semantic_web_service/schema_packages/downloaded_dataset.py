# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
"""Schema for downloaded datasets from the search ELN."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

import yaml
from nomad.datamodel.data import ArchiveSection, Schema, UseCaseElnCategory
from nomad.datamodel.metainfo.annotations import ELNAnnotation, ELNComponentEnum
from nomad.metainfo import Datetime, Quantity, SchemaPackage
from nomad.metainfo.metainfo import Section, SubSection

if TYPE_CHECKING:
    from nomad.datamodel.datamodel import EntryArchive
    from structlog.stdlib import BoundLogger

m_package = SchemaPackage()


class DownloadedFile(ArchiveSection):
    m_def = Section(label="Downloaded file")

    path = Quantity(
        type=str,
        description="Path of the file within this upload.",
        a_eln=ELNAnnotation(component=ELNComponentEnum.FileEditQuantity),
    )


class DownloadedDataset(Schema):
    """
    A standalone entry for a dataset downloaded from a public synchrotron
    catalogue, referencing the files that were downloaded.

    Created automatically by write_downloaded_dataset_entry(), called from
    MatchedDataset.normalize() once trigger_download succeeds -
    catalogue.icat.download_dataset_archive() does the actual download; this
    only records the outcome as its own browsable/searchable entry, separate
    from the DatasetSearchRequest that found it (which may match many
    datasets, across many searches, over time).
    """

    m_def = Section(label="Downloaded dataset", categories=[UseCaseElnCategory])

    dataset_id = Quantity(type=int, description="The catalogue-internal dataset id.")
    name = Quantity(type=str, description="Dataset title.")
    start_date = Quantity(type=Datetime, description="Start date-time of the dataset.")
    end_date = Quantity(type=Datetime, description="End date-time of the dataset.")
    instrument_name = Quantity(
        type=str, description="Name of the beamline or instrument."
    )
    technique_pids = Quantity(
        type=str,
        description=(
            "Comma-separated ESRFET technique IRIs associated with the dataset."
        ),
    )
    sample_name = Quantity(type=str, description="Name/description of the sample.")
    investigation_name = Quantity(
        type=str,
        description=(
            "Name (proposal/experiment session id) of the ICAT+ investigation "
            "this dataset belongs to."
        ),
    )
    investigation_title = Quantity(
        type=str,
        description="Title of the ICAT+ investigation this dataset belongs to.",
    )
    landing_page = Quantity(
        type=str,
        description="DOI-based landing page for the dataset (https://doi.org/<doi>).",
    )
    ids_status = Quantity(
        type=str,
        description=(
            "IDS online/archive status ('ONLINE', 'ARCHIVED', ...) at the time "
            "this dataset was downloaded."
        ),
    )
    downloaded_folder = Quantity(
        type=str,
        description="Path (within this upload) where the files were extracted.",
    )
    files = SubSection(
        section_def=DownloadedFile,
        repeats=True,
        description="The individual files extracted from the downloaded archive.",
    )


def downloaded_dataset_mainfile(downloaded_folder: str) -> str:
    """The raw-file path of the .archive.yaml that becomes this dataset's own
    DownloadedDataset entry - a sibling of the folder its files were
    extracted into (e.g. "dataset-874478618" -> "dataset-874478618.archive.yaml")."""
    return f"{downloaded_folder}.archive.yaml"


@dataclass
class DownloadedDatasetFields:
    """The descriptive DownloadedDataset fields carried over from the
    MatchedDataset that was downloaded - everything except the download
    outcome itself (downloaded_folder, extracted files), which
    write_downloaded_dataset_entry() takes separately."""

    dataset_id: int | None
    name: str | None
    start_date: date | datetime | None
    end_date: date | datetime | None
    instrument_name: str | None
    technique_pids: str | None
    sample_name: str | None
    investigation_name: str | None
    investigation_title: str | None
    landing_page: str | None
    ids_status: str | None


def write_downloaded_dataset_entry(
    archive: "EntryArchive",
    logger: "BoundLogger",
    fields: DownloadedDatasetFields,
    downloaded_folder: str,
    extracted_files: list[str],
) -> None:
    """Writes a new DownloadedDataset entry, as a raw .archive.yaml mainfile
    referencing the files trigger_download just extracted, and triggers NOMAD
    to process it into its own entry.

    This is the same write-raw-file-then-process_updated_raw_file() pattern
    NOMAD's own built-in Downloads section uses
    (nomad/datamodel/metainfo/downloads.py, Downloads.normalize()) for the
    equivalent "download files, then turn them into a new entry" case -
    there's no separate API for creating an entry directly from a schema's
    normalize() other than writing its mainfile and asking NOMAD to match it.
    """
    data = {
        "m_def": (
            "nomad_semantic_web_service.schema_packages.downloaded_dataset"
            ".DownloadedDataset"
        ),
        "dataset_id": fields.dataset_id,
        "name": fields.name,
        "start_date": fields.start_date.isoformat() if fields.start_date else None,
        "end_date": fields.end_date.isoformat() if fields.end_date else None,
        "instrument_name": fields.instrument_name,
        "technique_pids": fields.technique_pids,
        "sample_name": fields.sample_name,
        "investigation_name": fields.investigation_name,
        "investigation_title": fields.investigation_title,
        "landing_page": fields.landing_page,
        "ids_status": fields.ids_status,
        "downloaded_folder": downloaded_folder,
        "files": [
            {"path": f"{downloaded_folder}/{file_name}"}
            for file_name in extracted_files
        ],
    }
    data = {key: value for key, value in data.items() if value not in (None, "")}

    mainfile = downloaded_dataset_mainfile(downloaded_folder)
    with archive.m_context.raw_file(mainfile, "w") as f:
        yaml.safe_dump({"data": data}, f)

    archive.m_context.process_updated_raw_file(mainfile, allow_modify=True)
    logger.info("created downloaded dataset entry", mainfile=mainfile)


m_package.__init_metainfo__()
