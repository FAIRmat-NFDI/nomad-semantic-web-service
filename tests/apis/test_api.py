# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
"""Test the FastAPI client."""

from fastapi.testclient import TestClient


def test_importing_api():
    from nomad_semantic_web_service.apis import api_entry_point

    assert api_entry_point.prefix == "semantic-web-service"
    assert api_entry_point.name == "SemanticWebServiceAPI"


def test_health():
    from nomad_semantic_web_service.apis.api import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_map_panet_to_esrfet():
    from nomad_semantic_web_service.apis.api import app

    client = TestClient(app)
    response = client.get(
        "/map", params={"term": "PaNET01196", "source": "PANET", "target": "ESRFET"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mappings"]
    assert body["targetTerm"] == body["mappings"][0]["targetTerm"]


def test_catalogue_datasets_proxy_forwards_technique_pids(monkeypatch):
    import nomad_semantic_web_service.apis.api as api_module

    captured = {}

    def fake_fetch(
        start_date, end_date, instrument_name=None, technique_pids=None, **kwargs
    ):
        captured["kwargs"] = {
            "instrument_name": instrument_name,
            "technique_pids": technique_pids,
        }
        return [{"id": 1, "name": "demo"}]

    monkeypatch.setattr(api_module, "fetch_icat_catalogue_datasets", fake_fetch)

    client = TestClient(api_module.app)
    response = client.get(
        "/catalogue/datasets",
        params={
            "startDate": "2023-02-09",
            "endDate": "2023-02-13",
            "techniquePids": "https://w3id.org/PaN/ESRFET#XAS",
            "instrumentName": "BM23",
        },
    )
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "demo"}]
    # real ICAT+ /catalogue/datasets supports techniquePids server-side, so the
    # proxy forwards it (it just matches nothing on unannotated public data).
    assert captured["kwargs"]["technique_pids"] == "https://w3id.org/PaN/ESRFET#XAS"
    assert captured["kwargs"]["instrument_name"] == "BM23"


def test_download_dataset(monkeypatch):
    import nomad_semantic_web_service.apis.api as api_module

    monkeypatch.setattr(
        api_module,
        "download_dataset_archive",
        lambda dataset_id, file_extensions=None: b"zip-bytes",
    )

    client = TestClient(api_module.app)
    response = client.get("/ids/data/download", params={"datasetIds": 874478618})
    assert response.status_code == 200
    assert response.content == b"zip-bytes"
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="dataset-874478618.zip"' in response.headers["content-disposition"]


def test_download_dataset_no_matching_files(monkeypatch):
    import nomad_semantic_web_service.apis.api as api_module

    def raise_no_match(dataset_id, file_extensions=None):
        raise ValueError("No datafiles match the requested file extensions.")

    monkeypatch.setattr(api_module, "download_dataset_archive", raise_no_match)

    client = TestClient(api_module.app)
    response = client.get(
        "/ids/data/download",
        params={"datasetIds": 874478618, "fileExtensions": "nonexistent"},
    )
    assert response.status_code == 404
