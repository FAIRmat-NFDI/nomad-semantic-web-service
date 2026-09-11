# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
import os.path
from datetime import datetime, timezone
from types import SimpleNamespace

import structlog
from nomad.client import normalize_all, parse
from nomad.datamodel.context import ServerContext

import nomad_semantic_web_service.schema_packages.schema as schema_module
from nomad_semantic_web_service.catalogue.facilities import FacilityOntology
from nomad_semantic_web_service.schema_packages.schema import DatasetSearchRequest


def test_dataset_search_request_esrfet():
    test_file = os.path.join("tests", "data", "test.archive.yaml")
    entry_archive = parse(test_file)[0]
    normalize_all(entry_archive)

    data = entry_archive.data
    assert data.resolved_technique_term == "https://w3id.org/PaN/ESRFET#XAS"
    assert data.mapping_warning is None
    # Both 1001 (FeK_align) and 1002 (DAC6-QMo) carry the XAS technique PID.
    print(data.m_to_dict())
    assert len(data.matched_datasets) == 2
    assert data.matched_datasets[0].name == "0001"
    assert data.matched_datasets[0].sample_name == "FeK_align"
    assert data.matched_datasets[0].technique_pids == "https://w3id.org/PaN/ESRFET#XAS"
    assert data.matched_datasets[0].investigation_name == "IH-HC-3846"
    assert (
        data.matched_datasets[0].investigation_title
        == "High pressure EXAFS study on FeTiO3"
    )
    # parse()/normalize_all() run outside ServerContext, so facility ontology
    # discovery (an outbound HTTP call) is skipped, like the real ICAT+ call.
    assert data.detected_technique_ontology is None
    assert data.vocabulary_warning is None


def test_dataset_search_request_panet():
    test_file = os.path.join("tests", "data", "test_panet.archive.yaml")
    entry_archive = parse(test_file)[0]
    normalize_all(entry_archive)

    data = entry_archive.data
    # query_panet_to_esrfet() finds the target in the ontology's own purl.org
    # namespace; resolve_technique_term() canonicalizes it to the w3id.org form
    # used on ICAT+ dataset records, so resolved_technique_term is directly
    # usable as a techniquePids filter (same w3id form as the ESRFET path).
    assert data.resolved_technique_term == "https://w3id.org/PaN/ESRFET#XAS"
    assert data.mapping_warning is None
    # Both 1001 and 1002 carry the XAS technique PID in FAKE_DATASETS.
    assert len(data.matched_datasets) == 2


def test_dataset_search_request_uses_default_dates():
    """start_date/end_date are left unset, relying on the Quantity defaults.

    Regression test: an unset Quantity default is returned as the raw literal
    (a str here) rather than coerced through the Datetime type, which crashed
    search_local_datasets()'s `dataset['endDate'] <= end_date` comparison
    until normalize() started re-assigning start_date/end_date to themselves
    to force the coercion.
    """
    test_file = os.path.join("tests", "data", "test_default_dates.archive.yaml")
    entry_archive = parse(test_file)[0]
    normalize_all(entry_archive)

    data = entry_archive.data
    assert data.start_date.isoformat() == "2021-01-01T00:00:00+00:00"
    assert data.end_date.isoformat() == "2022-12-31T23:59:59+00:00"
    assert len(data.matched_datasets) == 2


def test_repeated_normalize_does_not_discard_matched_dataset_state():
    """Regression test: removing the old trigger_search confirmation step meant
    the search runs automatically on every save. Without the search_key cache,
    a second normalize() call with unchanged inputs would rebuild
    matched_datasets from scratch, discarding e.g. an in-progress
    trigger_download/file_extensions_filter set on an existing item before
    that item ever got a chance to act on it."""
    test_file = os.path.join("tests", "data", "test.archive.yaml")
    entry_archive = parse(test_file)[0]
    normalize_all(entry_archive)

    data = entry_archive.data
    first_key = data.search_key
    data.matched_datasets[0].file_extensions_filter = "json"

    normalize_all(entry_archive)

    assert data.search_key == first_key
    assert data.matched_datasets[0].file_extensions_filter == "json"


def test_matched_dataset_download_skipped_offline():
    """trigger_download on a MatchedDataset is a no-op outside ServerContext,
    matching the use_real_icat guard on the parent DatasetSearchRequest."""
    test_file = os.path.join("tests", "data", "test.archive.yaml")
    entry_archive = parse(test_file)[0]
    normalize_all(entry_archive)

    matched_dataset = entry_archive.data.matched_datasets[0]
    matched_dataset.trigger_download = True
    matched_dataset.normalize(entry_archive, structlog.get_logger())

    assert matched_dataset.trigger_download is False
    assert matched_dataset.downloaded_folder is None
    assert matched_dataset.downloaded_files is None


def test_detect_technique_vocabulary_matches_manual_selection(monkeypatch):
    monkeypatch.setattr(
        schema_module,
        "discover_facility_ontologies",
        lambda name: [
            FacilityOntology(
                name="ESRFET",
                uri="https://w3id.org/PaN/ESRFET",
                applies_to=("technique",),
            )
        ],
    )

    request = DatasetSearchRequest(synchrotron="ESRF", vocabulary="ESRFET")
    request._detect_technique_vocabulary(structlog.get_logger())

    assert request.detected_technique_ontology == "ESRFET"
    assert request.vocabulary_warning is None


def test_detect_technique_vocabulary_mismatch_warns_but_does_not_override(monkeypatch):
    monkeypatch.setattr(
        schema_module,
        "discover_facility_ontologies",
        lambda name: [
            FacilityOntology(
                name="PaNET",
                uri="http://purl.org/pan-science/PaNET",
                applies_to=("technique",),
            )
        ],
    )

    request = DatasetSearchRequest(synchrotron="ESRF", vocabulary="ESRFET")
    request._detect_technique_vocabulary(structlog.get_logger())

    assert request.detected_technique_ontology == "PaNET"
    # The manual vocabulary selection is never overridden automatically.
    assert request.vocabulary == "ESRFET"
    assert "vocabulary is set to ESRFET" in request.vocabulary_warning


def test_detect_technique_vocabulary_no_technique_concept_advertised(monkeypatch):
    monkeypatch.setattr(schema_module, "discover_facility_ontologies", lambda name: [])

    request = DatasetSearchRequest(synchrotron="ESRF", vocabulary="ESRFET")
    request._detect_technique_vocabulary(structlog.get_logger())

    assert request.detected_technique_ontology is None
    assert request.vocabulary_warning is None


def test_detect_technique_vocabulary_discovery_failure_is_a_warning_not_a_crash(
    monkeypatch,
):
    def raise_network_error(name):
        raise RuntimeError("network down")

    monkeypatch.setattr(
        schema_module, "discover_facility_ontologies", raise_network_error
    )

    request = DatasetSearchRequest(synchrotron="ESRF", vocabulary="ESRFET")
    request._detect_technique_vocabulary(structlog.get_logger())  # must not raise

    assert request.detected_technique_ontology is None
    assert request.vocabulary_warning is None


def _fake_real_dataset(dataset_id: int, name: str) -> dict:
    return {
        "id": dataset_id,
        "name": name,
        "startDate": datetime(2021, 3, 18, tzinfo=timezone.utc),
        "endDate": datetime(2021, 3, 18, tzinfo=timezone.utc),
        "instrumentName": "ID21",
        "sampleName": "demo sample",
    }


def test_run_search_require_online_filters_out_archived_matches(monkeypatch):
    monkeypatch.setattr(
        schema_module,
        "fetch_icat_catalogue_datasets",
        lambda *args, **kwargs: [
            _fake_real_dataset(1, "online-dataset"),
            _fake_real_dataset(2, "archived-dataset"),
        ],
    )
    monkeypatch.setattr(
        schema_module,
        "get_datasets_status",
        lambda dataset_ids: {1: "ONLINE", 2: "ARCHIVED"},
    )

    request = DatasetSearchRequest(
        synchrotron="ESRF",
        vocabulary="ESRFET",
        technique_term="XAS",
        use_real_icat=True,
        require_online=True,
        resolved_technique_term="https://w3id.org/PaN/ESRFET#XAS",
    )
    fake_archive = SimpleNamespace(m_context=ServerContext(upload=None))
    request._run_search(fake_archive, structlog.get_logger())

    assert len(request.matched_datasets) == 1
    assert request.matched_datasets[0].dataset_id == 1
    assert request.matched_datasets[0].ids_status == "ONLINE"


def test_run_search_without_require_online_keeps_archived_matches_but_flags_them(
    monkeypatch,
):
    monkeypatch.setattr(
        schema_module,
        "fetch_icat_catalogue_datasets",
        lambda *args, **kwargs: [
            _fake_real_dataset(1, "online-dataset"),
            _fake_real_dataset(2, "archived-dataset"),
        ],
    )
    monkeypatch.setattr(
        schema_module,
        "get_datasets_status",
        lambda dataset_ids: {1: "ONLINE", 2: "ARCHIVED"},
    )

    request = DatasetSearchRequest(
        synchrotron="ESRF",
        vocabulary="ESRFET",
        technique_term="XAS",
        use_real_icat=True,
        require_online=False,
        resolved_technique_term="https://w3id.org/PaN/ESRFET#XAS",
    )
    fake_archive = SimpleNamespace(m_context=ServerContext(upload=None))
    request._run_search(fake_archive, structlog.get_logger())

    assert len(request.matched_datasets) == 2
    statuses = {m.dataset_id: m.ids_status for m in request.matched_datasets}
    assert statuses == {1: "ONLINE", 2: "ARCHIVED"}


def test_run_search_require_online_fails_open_when_status_lookup_errors(monkeypatch):
    monkeypatch.setattr(
        schema_module,
        "fetch_icat_catalogue_datasets",
        lambda *args, **kwargs: [_fake_real_dataset(1, "some-dataset")],
    )

    def raise_error(dataset_ids):
        raise RuntimeError("IDS status endpoint down")

    monkeypatch.setattr(schema_module, "get_datasets_status", raise_error)

    request = DatasetSearchRequest(
        synchrotron="ESRF",
        vocabulary="ESRFET",
        technique_term="XAS",
        use_real_icat=True,
        require_online=True,
        resolved_technique_term="https://w3id.org/PaN/ESRFET#XAS",
    )
    fake_archive = SimpleNamespace(m_context=ServerContext(upload=None))
    request._run_search(fake_archive, structlog.get_logger())

    # A failed status lookup must not silently empty out matched_datasets.
    assert len(request.matched_datasets) == 1
    assert request.matched_datasets[0].ids_status is None
