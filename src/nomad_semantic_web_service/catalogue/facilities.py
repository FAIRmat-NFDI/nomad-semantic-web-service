# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
"""Utilities for interacting with the ESRF ICAT facility API endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

ESRF_FACILITIES_URL = "https://icatplus.esrf.fr/facilities"


@dataclass(frozen=True)
class FacilityOntology:
    name: str
    uri: str
    applies_to: tuple[str, ...]


def fetch_facilities(client: httpx.Client | None = None) -> list[dict[str, Any]]:
    close_client = client is None
    client = client or httpx.Client(timeout=10)
    try:
        response = client.get(
            ESRF_FACILITIES_URL, headers={"accept": "application/json"}
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    finally:
        if close_client:
            client.close()


def find_facility_ontologies(
    facility_name: str,
    facilities: list[dict[str, Any]],
) -> list[FacilityOntology]:
    for facility in facilities:
        if str(facility.get("name", "")).upper() != facility_name.upper():
            continue

        ontologies = facility.get("ontologies", [])
        if not isinstance(ontologies, list):
            return []

        return [
            FacilityOntology(
                name=str(ontology.get("name", "")),
                uri=str(ontology.get("uri", "")),
                applies_to=tuple(str(value) for value in ontology.get("appliesTo", [])),
            )
            for ontology in ontologies
            if isinstance(ontology, dict)
            and ontology.get("name")
            and ontology.get("uri")
        ]

    return []


def discover_facility_ontologies(
    facility_name: str,
    client: httpx.Client | None = None,
) -> list[FacilityOntology]:
    return find_facility_ontologies(facility_name, fetch_facilities(client))


def ontology_for_concept(
    ontologies: list[FacilityOntology],
    concept: str,
) -> FacilityOntology | None:
    for ontology in ontologies:
        if concept in ontology.applies_to:
            return ontology
    return None
