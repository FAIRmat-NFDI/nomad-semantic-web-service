# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
"""Test ICAT catalogue search functionality."""

from nomad_semantic_web_service.catalogue.search import (
    investigation_field,
    technique_pids_of,
)


def test_technique_pids_of():
    dataset = {
        "techniques": [
            {"id": 1, "pid": "PaNET:PaNET01012", "name": "x-ray probe"},
            {"id": 2, "pid": None, "name": "no pid"},
        ]
    }
    assert technique_pids_of(dataset) == ["PaNET:PaNET01012"]


def test_technique_pids_of_missing():
    assert technique_pids_of({}) == []


def test_investigation_field():
    dataset = {"investigation": {"name": "ee1234", "title": "A great experiment"}}
    assert investigation_field(dataset, "name") == "ee1234"
    assert investigation_field(dataset, "title") == "A great experiment"


def test_investigation_field_missing_key():
    assert investigation_field({"investigation": {"name": "ee1234"}}, "title") is None


def test_investigation_field_no_investigation():
    assert investigation_field({}, "name") is None


def test_investigation_field_malformed_investigation():
    assert investigation_field({"investigation": "not-a-dict"}, "name") is None
