"""Opt-in tests against the real icatplus.esrf.fr, not mocks.

Every other test in this suite uses httpx.MockTransport/monkeypatch, so none
of them can catch upstream API drift - which is exactly how the switch from
/catalogue/public/datasets to /catalogue/datasets went unnoticed until it
404'd in production. These tests hit the real service to guard against that
recurring. Excluded from normal runs via the `live` marker (see
pyproject.toml's `addopts`); run explicitly with `pytest -m live`.
"""

from datetime import date

import httpx
import pytest

from nomad_semantic_web_service.catalogue.icat import (
    DatasetNotOnlineError,
    download_dataset_archive,
    fetch_icat_catalogue_datasets,
    get_anonymous_session_id,
    get_datasets_status,
    list_datafiles,
)

pytestmark = pytest.mark.live

# Matches oscarsSemanticWebService's own confirmed-working example
# (README.md / app/agent.py DEFAULT_* constants), so a failure here means
# either the endpoint or this default example query has broken again.
BM23_START_DATE = date(2023, 2, 9)
BM23_END_DATE = date(2023, 2, 13)
BM23_INSTRUMENT = "BM23"


def test_live_fetch_icat_catalogue_datasets_bm23():
    datasets = fetch_icat_catalogue_datasets(
        start_date=BM23_START_DATE,
        end_date=BM23_END_DATE,
        instrument_name=BM23_INSTRUMENT,
    )

    assert isinstance(datasets, list)
    if not datasets:
        pytest.skip(
            "ICAT+ returned no BM23 datasets for the reference window; "
            "cannot exercise the download chain below."
        )
    assert all("id" in dataset for dataset in datasets)


def test_live_download_chain_for_first_bm23_dataset():
    """Exercises the full anonymous download path used by
    MatchedDataset.normalize()'s trigger_download: session -> file listing ->
    filtered content download. Downloads only files matching a narrow
    extension filter, not the whole (potentially large) dataset."""
    datasets = fetch_icat_catalogue_datasets(
        start_date=BM23_START_DATE,
        end_date=BM23_END_DATE,
        instrument_name=BM23_INSTRUMENT,
    )
    if not datasets:
        pytest.skip("ICAT+ returned no BM23 datasets for the reference window.")

    dataset_id = datasets[0]["id"]

    with httpx.Client(timeout=30) as client:
        session_id = get_anonymous_session_id(dataset_id, client=client)
        assert session_id

        datafiles = list_datafiles(dataset_id, session_id, client=client)
    assert isinstance(datafiles, list)
    if not datafiles:
        pytest.skip(f"Dataset {dataset_id} has no listed datafiles.")

    extensions = {
        name.rsplit(".", 1)[-1].lower()
        for datafile in datafiles
        if "." in (name := datafile.get("name") or "")
    }
    if not extensions:
        pytest.skip(f"Dataset {dataset_id}'s datafiles have no file extensions.")

    # Any one real extension confirms the session/listing/download chain
    # works end-to-end without pulling the whole (possibly large) dataset.
    content = download_dataset_archive(
        dataset_id, file_extensions=[next(iter(extensions))]
    )
    assert content


def test_live_archived_dataset_raises_not_online_instead_of_a_bare_404():
    """Regression test for the reported bug: real ICAT+ archives older public
    datasets to tape, and downloading one 404s with DataNotOnlineException
    until restored. Confirmed empirically that DatasetSearchRequest's own
    default search window (2021-01-01..2022-12-31) lands squarely in archived
    territory. download_dataset_archive() must surface this as
    DatasetNotOnlineError, not let the raw httpx.HTTPStatusError propagate."""
    datasets = fetch_icat_catalogue_datasets(
        start_date=date(2021, 1, 1),
        end_date=date(2021, 6, 30),
        limit=20,
    )
    if not datasets:
        pytest.skip("ICAT+ returned no datasets for the 2021 H1 reference window.")

    dataset_ids = [dataset["id"] for dataset in datasets]
    statuses = get_datasets_status(dataset_ids)
    archived_ids = [
        dataset_id for dataset_id, status in statuses.items() if status != "ONLINE"
    ]
    if not archived_ids:
        pytest.skip("All datasets in the 2021 H1 window are currently ONLINE.")

    with pytest.raises(DatasetNotOnlineError) as exc_info:
        download_dataset_archive(archived_ids[0])

    assert exc_info.value.dataset_id == archived_ids[0]
    assert exc_info.value.status != "ONLINE"
