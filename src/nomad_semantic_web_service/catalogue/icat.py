# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
"""Functionality to interact with the ESRF ICAT catalogue API."""

from __future__ import annotations

import re
import zipfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

ICAT_BASE_URL = "https://icatplus.esrf.fr"
ICAT_DATASETS_PATH = "/catalogue/datasets"
ICAT_DATASETS_URL = ICAT_BASE_URL + ICAT_DATASETS_PATH
IDS_DOWNLOAD_URL = ICAT_BASE_URL + "/ids/data/download"


def serialize_date_for_icat_query(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def serialize_datetime_for_query(value: datetime) -> str:
    serialized = value.isoformat()
    if value.tzinfo is not None and value.utcoffset() == timezone.utc.utcoffset(value):
        return serialized.replace("+00:00", "Z")
    return serialized


def landing_page_for_dataset(dataset: dict[str, Any]) -> str | None:
    """Resolves a public landing-page URL for a real ICAT+ dataset record.

    `dataset['location']` is an internal ESRF storage path, not a public URL.
    `dataset['investigation']['doi']` (e.g. "10.15151/ESRF-ES-750932592") is the
    durable, public identifier ICAT+ itself uses for datasets (see the
    `/doi/{prefix}/{suffix}/datasets` route in https://icatplus.esrf.fr/swagger.json),
    so it's resolved through the standard DOI resolver instead.
    """
    doi = dataset.get("investigation", {}).get("doi")
    return f"https://doi.org/{doi}" if doi else None


def build_icat_catalogue_dataset_params(
    start_date: date | datetime,
    end_date: date | datetime,
    instrument_name: str | None,
    technique_pids: str | None = None,
    limit: int = 100,
) -> dict[str, str]:
    params = {
        "startDate": serialize_date_for_icat_query(start_date),
        "endDate": serialize_date_for_icat_query(end_date),
        "limit": str(limit),
        "sortBy": "STARTDATE",
        # Newest datasets first (sortOrder "-1" descending). Recent beamtimes use
        # the current export conventions, so the first results are the most
        # likely to convert cleanly; older exports can differ.
        "sortOrder": "-1",
    }
    if instrument_name:
        params["instrumentName"] = instrument_name
    if technique_pids:
        params["techniquePids"] = technique_pids
    return params


def fetch_icat_catalogue_datasets(  # noqa: PLR0913, PLR0917
    start_date: date | datetime,
    end_date: date | datetime,
    instrument_name: str | None = None,
    technique_pids: str | None = None,
    limit: int = 100,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Lists real ICAT+ datasets from `GET /catalogue/datasets` (the catalogue
    listing route that actually exists on icatplus.esrf.fr).

    Filters by date range, instrument, and optionally `technique_pids`: the
    route documents a `techniquePids` filter (in swagger.json) and applies it
    server-side. It only matches datasets that are annotated with technique
    PIDs, though - public BM23 records currently have an empty `techniques[]`,
    so a technique filter returns nothing for them and callers narrow by
    beamline instead (see the demonstrator's ESRF_ICAT.md). The separate
    `/catalogue/public/datasets` route does not exist on the live server (404,
    undocumented) and is not used.
    """
    close_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(
            ICAT_DATASETS_URL,
            params=build_icat_catalogue_dataset_params(
                start_date=start_date,
                end_date=end_date,
                instrument_name=instrument_name,
                technique_pids=technique_pids,
                limit=limit,
            ),
            headers={"accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    finally:
        if close_client:
            client.close()


def get_anonymous_session_id(dataset_id: int, client: httpx.Client) -> str:
    """Obtains an anonymous ICAT+ session id for a public dataset.

    ICAT+ has no dedicated "create anonymous session" endpoint (`POST /session`
    requires real credentials). `GET /ids/data/download` accepts unauthenticated
    requests for public datasets and redirects to `ids.esrf.fr` with a freshly
    minted, anonymous `sessionId` query param (confirmed empirically: the
    route's swagger security scheme is `[{bearerAuth: []}, {}]`, i.e. auth is
    optional) - this extracts that session id so it can also be used to list
    a dataset's individual files (`/catalogue/{sessionId}/dataset/id/.../datafile`)
    for extension-based filtering.
    """
    response = client.get(
        IDS_DOWNLOAD_URL,
        params={"datasetIds": dataset_id, "inline": "false"},
        follow_redirects=False,
    )
    location = response.headers.get("location", "")
    session_ids = parse_qs(urlparse(location).query).get("sessionId")
    if not session_ids:
        raise ValueError(
            f"Could not obtain an anonymous ICAT+ session (status {response.status_code})."
        )
    return session_ids[0]


class DatasetNotOnlineError(Exception):
    """Raised when a dataset's files are archived (e.g. on tape) rather than
    immediately downloadable. ICAT+'s IDS backend restores archived datasets
    on request, but that is asynchronous - it was empirically observed to
    still take longer than 40s after both a plain download attempt (whose own
    error claims restoration is "requested automatically") and an explicit
    `POST .../datasets/restore`. There is no synchronous way to wait this out
    within a single request; callers should surface `status` to the user and
    let them retry later, not treat this as a transient/generic failure.
    """

    def __init__(self, dataset_id: int, status: str):
        self.dataset_id = dataset_id
        self.status = status
        super().__init__(
            f"Dataset {dataset_id} is not online (status: {status}). A "
            "restore has been requested; tape-archived data can take "
            "minutes to hours to become downloadable - retry later."
        )


def get_dataset_status(dataset_id: int, session_id: str, client: httpx.Client) -> str:
    """Returns a single dataset's IDS status (e.g. "ONLINE", "ARCHIVED",
    "RESTORING")."""
    response = client.get(
        f"{ICAT_BASE_URL}/ids/{session_id}/datasets/status",
        params={"datasetIds": str(dataset_id)},
    )
    response.raise_for_status()
    statuses = response.json()
    return statuses[0] if statuses else "UNKNOWN"


def get_datasets_status(
    dataset_ids: list[int], client: httpx.Client | None = None
) -> dict[int, str]:
    """Returns IDS status for several datasets in one request. Mints its own
    anonymous session (against the first id - sessions aren't dataset-scoped)
    since this is meant to annotate search results, not extend an
    already-open download flow (see get_dataset_status() for that case)."""
    if not dataset_ids:
        return {}
    close_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        session_id = get_anonymous_session_id(dataset_ids[0], client=client)
        response = client.get(
            f"{ICAT_BASE_URL}/ids/{session_id}/datasets/status",
            params={"datasetIds": ",".join(str(i) for i in dataset_ids)},
        )
        response.raise_for_status()
        return dict(zip(dataset_ids, response.json()))
    finally:
        if close_client:
            client.close()


def request_dataset_restore(
    dataset_id: int, session_id: str, client: httpx.Client
) -> None:
    """Queues an IDS restore for an archived dataset. Fire-and-forget: IDS
    responds immediately (redirecting to where the eventual download will
    land) without waiting for the actual tape restoration - see
    DatasetNotOnlineError's docstring for why callers can't just wait here."""
    client.post(
        f"{ICAT_BASE_URL}/ids/{session_id}/datasets/restore",
        params={"datasetIds": str(dataset_id)},
        json={"name": "anonymous", "email": "anonymous@nomad-oasis"},
        follow_redirects=False,
    )


def list_datafiles(
    dataset_id: int, session_id: str, client: httpx.Client
) -> list[dict[str, Any]]:
    """Lists the individual files of a dataset, e.g. to filter by extension
    before downloading. Each entry has `id`, `name` (includes the extension),
    `fileSize`, and `location` (an internal storage path, not a public URL)."""
    response = client.get(
        f"{ICAT_BASE_URL}/catalogue/{session_id}/dataset/id/{dataset_id}/datafile"
    )
    response.raise_for_status()
    return [item["Datafile"] for item in response.json() if "Datafile" in item]


def matches_file_extensions(
    datafile: dict[str, Any], file_extensions: set[str]
) -> bool:
    name = datafile.get("name") or ""
    return any(name.lower().endswith(f".{ext}") for ext in file_extensions)


def download_dataset_archive(
    dataset_id: int,
    file_extensions: list[str] | None = None,
    client: httpx.Client | None = None,
) -> bytes:
    """Downloads a public ICAT+ dataset as a zip archive, anonymously.

    If `file_extensions` is given (e.g. `["h5", "edf"]`), only datafiles whose
    name ends with one of them (case-insensitive) are included; otherwise the
    whole dataset is downloaded. Raises `ValueError` if a filter matches no
    files, or `DatasetNotOnlineError` if the dataset is archived rather than
    immediately downloadable (confirmed empirically: real ICAT+ archives
    older public datasets to tape and 404s `GET .../data/download` for them
    with `DataNotOnlineException` until restored).
    """
    close_client = client is None
    client = client or httpx.Client(timeout=120)
    try:
        session_id = get_anonymous_session_id(dataset_id, client=client)
        status = get_dataset_status(dataset_id, session_id, client=client)
        if status != "ONLINE":
            request_dataset_restore(dataset_id, session_id, client=client)
            raise DatasetNotOnlineError(dataset_id, status)

        if file_extensions:
            extensions = {ext.lower().lstrip(".") for ext in file_extensions}
            datafiles = list_datafiles(dataset_id, session_id, client=client)
            datafile_ids = [
                datafile["id"]
                for datafile in datafiles
                if matches_file_extensions(datafile, extensions)
            ]
            if not datafile_ids:
                raise ValueError(
                    f"No datafiles in dataset {dataset_id} match extensions "
                    f"{sorted(extensions)}."
                )
            params = {
                "datafileIds": ",".join(str(i) for i in datafile_ids),
                "inline": "false",
            }
        else:
            params = {
                "datasetIds": str(dataset_id),
                "inline": "false",
            }

        response = client.get(IDS_DOWNLOAD_URL, params=params, follow_redirects=True)
        response.raise_for_status()
        return response.content
    finally:
        if close_client:
            client.close()


def looks_like_zip(content: bytes) -> bool:
    """True if *content* starts with the ZIP local-file-header magic ``PK\\x03\\x04``."""
    return content[:4] == b"PK\x03\x04"


def download_datafiles(
    dataset_id: int,
    file_extensions: list[str] | None = None,
    client: httpx.Client | None = None,
) -> list[tuple[str, bytes]]:
    """Download a public dataset's files and return ``(name, bytes)`` pairs.

    The canonical download primitive used by both the ELN schema and the
    on-disk ``download_and_extract``. Anonymous, optionally filtered to
    *file_extensions* (e.g. ``["h5"]``). Raises ``DatasetNotOnlineError`` for
    tape-archived datasets and ``ValueError`` if a filter matches nothing.

    IDS returns a **zip** when the whole dataset (or several files) is
    requested, but the **raw file itself** when exactly one datafile id is
    requested (e.g. an ID21 dataset holding a single ``.h5``). This handles
    both: a zip is unpacked via ``extract_zip_members``; a raw single-file
    response is paired with the name of the one datafile requested.
    """
    close_client = client is None
    client = client or httpx.Client(timeout=120)
    try:
        session_id = get_anonymous_session_id(dataset_id, client=client)
        status = get_dataset_status(dataset_id, session_id, client=client)
        if status != "ONLINE":
            request_dataset_restore(dataset_id, session_id, client=client)
            raise DatasetNotOnlineError(dataset_id, status)

        datafiles = list_datafiles(dataset_id, session_id, client=client)
        if file_extensions:
            extensions = {ext.lower().lstrip(".") for ext in file_extensions}
            selected = [
                datafile
                for datafile in datafiles
                if matches_file_extensions(datafile, extensions)
            ]
            if not selected:
                raise ValueError(
                    f"No datafiles in dataset {dataset_id} match extensions "
                    f"{sorted(extensions)}."
                )
            params = {
                "datafileIds": ",".join(str(f["id"]) for f in selected),
                "inline": "false",
            }
        else:
            selected = datafiles
            params = {"datasetIds": str(dataset_id), "inline": "false"}

        response = client.get(IDS_DOWNLOAD_URL, params=params, follow_redirects=True)
        response.raise_for_status()
        content = response.content

        if looks_like_zip(content):
            return extract_zip_members(content)
        # Single-file (raw) response: name it after the one requested datafile.
        name = (
            selected[0].get("name")
            if len(selected) == 1
            else f"dataset-{dataset_id}.bin"
        )
        return [(normalize_zip_member_name(str(name)), content)]
    finally:
        if close_client:
            client.close()


def download_and_extract(
    dataset_id: int,
    dest_dir: Path,
    file_extensions: list[str] | None = None,
    client: httpx.Client | None = None,
) -> list[Path]:
    """Download a public dataset and extract its files to *dest_dir* on disk.

    On-disk wrapper over ``download_datafiles`` (which handles both the zip and
    single-raw-file IDS responses). Returns the written file paths. Raises
    ``DatasetNotOnlineError`` for tape-archived datasets.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for member_name, data in download_datafiles(
        dataset_id, file_extensions=file_extensions, client=client
    ):
        out = dest_dir / Path(member_name).name
        out.write_bytes(data)
        written.append(out)
    return written


def normalize_zip_member_name(name: str) -> str:
    """Normalizes a zip member name into a safe relative path.

    Real ICAT+ archives have been observed to contain entries with doubled
    slashes (e.g. "poi28997_35602//35602_args.json") and leading slashes,
    either of which `nomad.common.is_safe_relative_path()` rejects outright
    (it requires no leading "/" and no "//"), which would otherwise crash
    `archive.m_context.raw_file()`/`raw_create_directory()` calls.
    """
    collapsed = re.sub(r"/+", "/", name)
    return collapsed.lstrip("/")


def extract_zip_members(content: bytes) -> list[tuple[str, bytes]]:
    """Extracts a zip archive's regular files (skipping directory entries) in
    place, in memory. Returns `(member_name, data)` pairs, in archive order,
    with member names normalized via `normalize_zip_member_name()`.

    Separated from any actual upload/filesystem writing so it can be tested
    without a NOMAD upload context.
    """
    members = []
    with zipfile.ZipFile(BytesIO(content)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            with archive.open(info) as member_file:
                members.append(
                    (normalize_zip_member_name(info.filename), member_file.read())
                )
    return members
