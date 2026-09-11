import io
from datetime import datetime, timezone
from types import SimpleNamespace

import structlog
import yaml

from nomad_semantic_web_service.schema_packages.downloaded_dataset import (
    DownloadedDatasetFields,
    downloaded_dataset_mainfile,
    write_downloaded_dataset_entry,
)


class _FakeFileWriter:
    def __init__(self, store: dict, path: str):
        self.store = store
        self.path = path
        self.buffer = io.StringIO()

    def __enter__(self):
        return self.buffer

    def __exit__(self, *exc_info):
        self.store[self.path] = self.buffer.getvalue()
        return False


class FakeUploadContext:
    def __init__(self):
        self.written_files: dict[str, str] = {}
        self.processed_raw_files: list[tuple[str, bool]] = []

    def raw_file(self, path: str, mode: str = "r"):
        assert mode == "w"
        return _FakeFileWriter(self.written_files, path)

    def process_updated_raw_file(self, path: str, allow_modify: bool = False) -> None:
        self.processed_raw_files.append((path, allow_modify))


def test_downloaded_dataset_mainfile():
    assert (
        downloaded_dataset_mainfile("dataset-874478618")
        == "dataset-874478618.archive.yaml"
    )


def test_write_downloaded_dataset_entry_writes_archive_yaml_and_triggers_processing():
    context = FakeUploadContext()
    archive = SimpleNamespace(m_context=context)

    write_downloaded_dataset_entry(
        archive,
        structlog.get_logger(),
        DownloadedDatasetFields(
            dataset_id=874478618,
            name="Demo dataset",
            start_date=datetime(2023, 2, 9, tzinfo=timezone.utc),
            end_date=datetime(2023, 2, 13, tzinfo=timezone.utc),
            instrument_name="BM23",
            technique_pids="https://w3id.org/PaN/ESRFET#XAS",
            sample_name="demo sample",
            investigation_name="ee1234",
            investigation_title="A great experiment",
            landing_page="https://doi.org/10.0000/DEMO",
            ids_status="ONLINE",
        ),
        downloaded_folder="dataset-874478618",
        extracted_files=["FeK_align_0001.h5", "metadata.json"],
    )

    mainfile = "dataset-874478618.archive.yaml"
    assert mainfile in context.written_files

    written = yaml.safe_load(context.written_files[mainfile])
    data = written["data"]
    assert data["m_def"] == (
        "nomad_semantic_web_service.schema_packages.downloaded_dataset"
        ".DownloadedDataset"
    )
    assert data["dataset_id"] == 874478618
    assert data["name"] == "Demo dataset"
    assert data["start_date"] == "2023-02-09T00:00:00+00:00"
    assert data["instrument_name"] == "BM23"
    assert data["downloaded_folder"] == "dataset-874478618"
    assert data["files"] == [
        {"path": "dataset-874478618/FeK_align_0001.h5"},
        {"path": "dataset-874478618/metadata.json"},
    ]

    assert context.processed_raw_files == [(mainfile, True)]


def test_write_downloaded_dataset_entry_omits_unset_fields():
    context = FakeUploadContext()
    archive = SimpleNamespace(m_context=context)

    write_downloaded_dataset_entry(
        archive,
        structlog.get_logger(),
        DownloadedDatasetFields(
            dataset_id=1,
            name=None,
            start_date=None,
            end_date=None,
            instrument_name=None,
            technique_pids=None,
            sample_name=None,
            investigation_name=None,
            investigation_title=None,
            landing_page=None,
            ids_status=None,
        ),
        downloaded_folder="dataset-1",
        extracted_files=["a.h5"],
    )

    data = yaml.safe_load(context.written_files["dataset-1.archive.yaml"])["data"]
    assert data.keys() == {"m_def", "dataset_id", "downloaded_folder", "files"}
