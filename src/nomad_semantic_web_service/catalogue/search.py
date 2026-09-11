# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from nomad_semantic_web_service.catalogue.demo_data import FAKE_DATASETS

# Note: this is the w3id.org IRI used in dataset records, distinct from
# catalogue.ontology.ESRFET_PURL_PREFIX (the purl.org namespace used internally
# by ESRFET.owl). canonical_technique_pid() translates purl.org -> w3id.org so
# user-supplied PURL-form IRIs match the w3id-form IRIs stored on datasets.
ESRFET = "https://w3id.org/PaN/ESRFET#"
ESRFET_PURL = "http://purl.org/pan-science/ESRFET#"


def normalize_esrfet_term(term: str) -> str:
    """Normalizes a user-supplied ESRFET term to the w3id.org IRI form used by
    dataset records (e.g. "XAS" or "ESRFET:XAS" -> "https://w3id.org/PaN/ESRFET#XAS")."""
    cleaned = term.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    if cleaned.startswith("ESRFET:"):
        cleaned = cleaned.split(":", 1)[1]
    if cleaned.startswith("#"):
        cleaned = cleaned[1:]
    return ESRFET + cleaned


def canonical_technique_pid(technique_pid: str) -> str:
    if technique_pid.startswith(ESRFET_PURL):
        return ESRFET + technique_pid.removeprefix(ESRFET_PURL)
    return technique_pid


def resolve_technique_term(term: str, vocabulary: str | None = None) -> dict[str, Any]:
    """Resolve a user technique term to an ESRFET IRI — the semantic step.

    * ``vocabulary="PANET"`` (or an auto-detected PaNET term) is mapped through
      the local ESRFET ontology via ``owl:equivalentClass``.
    * ``vocabulary="ESRFET"`` (or anything else) is normalized directly to the
      w3id.org ESRFET IRI form used on dataset records.

    When *vocabulary* is ``None`` it is auto-detected: a term that starts with
    ``PaNET`` (id, CURIE, or PaNET IRI) is treated as PANET, otherwise ESRFET.

    Returns ``{"input", "vocabulary", "resolved_iri", "relation", "mappings",
    "warning"}``. This is the single implementation shared by the ELN
    (``DatasetSearchRequest``), the REST layer, and the notebook — none of them
    should re-inline the map-or-normalize logic.
    """
    # Local import: ontology pulls in owlready2/rdflib, which we don't want to
    # load just by importing this module.
    from nomad_semantic_web_service.catalogue.ontology import query_panet_to_esrfet

    cleaned = term.strip()
    if vocabulary is None:
        vocabulary = "PANET" if cleaned.lower().startswith("panet") else "ESRFET"

    if vocabulary.upper() == "PANET":
        mappings = query_panet_to_esrfet(cleaned)
        # The ontology maps to ESRFET's purl.org namespace, but ICAT+ dataset
        # records are annotated with the w3id.org IRI form (verified: a
        # techniquePids search matches only w3id-form PIDs). Canonicalize so the
        # resolved IRI is directly usable as a search filter.
        resolved_iri = (
            canonical_technique_pid(mappings[0]["targetTerm"]) if mappings else None
        )
        return {
            "input": term,
            "vocabulary": "PANET",
            "resolved_iri": resolved_iri,
            "relation": mappings[0].get("relation") if mappings else None,
            "mappings": mappings,
            "warning": None
            if mappings
            else "No ESRFET mapping found for this PANET term.",
        }
    return {
        "input": term,
        "vocabulary": "ESRFET",
        "resolved_iri": normalize_esrfet_term(cleaned),
        "relation": "normalized",
        "mappings": [],
        "warning": None,
    }


def parse_technique_pids(technique_pids: str | None) -> set[str]:
    if not technique_pids:
        return set()
    return {
        canonical_technique_pid(pid.strip())
        for pid in technique_pids.split(",")
        if pid.strip()
    }


def technique_pids_of(dataset: dict[str, Any]) -> list[str]:
    """Extracts technique PIDs from a dataset record's `techniques` list
    (the shape used by both FAKE_DATASETS and real ICAT+ records)."""
    return [
        technique["pid"]
        for technique in dataset.get("techniques", [])
        if technique.get("pid")
    ]


def investigation_field(dataset: dict[str, Any], key: str) -> str | None:
    """Extracts a field from a dataset record's `investigation` sub-object
    (its ICAT+ proposal/experiment session) - e.g. "name" or "title". Present
    on real ICAT+ records and on FAKE_DATASETS (which mirrors that shape), but
    accessed defensively since `investigation` can be absent or malformed."""
    investigation = dataset.get("investigation")
    if not isinstance(investigation, dict):
        return None
    value = investigation.get(key)
    return str(value) if value else None


def search_local_datasets(
    start_date: date | datetime,
    end_date: date | datetime,
    technique_pids: str | None,
    instrument_name: str | None,
) -> list[dict[str, Any]]:
    requested_techniques = parse_technique_pids(technique_pids)
    requested_instrument = instrument_name.lower() if instrument_name else None

    return [
        dataset
        for dataset in FAKE_DATASETS
        if dataset["startDate"] >= start_date
        and dataset["endDate"] <= end_date
        and (
            not requested_techniques
            or requested_techniques.intersection(
                canonical_technique_pid(pid) for pid in technique_pids_of(dataset)
            )
        )
        and (
            requested_instrument is None
            or dataset["instrumentName"].lower() == requested_instrument
        )
    ]


# NOTE: there is deliberately no `search_icat_datasets` wrapper. Real-ICAT
# search is `catalogue.icat.fetch_icat_catalogue_datasets` called directly
# (the ELN's real branch and the REST proxy both call it); `search_local_datasets`
# above is the offline/demo counterpart over FAKE_DATASETS.
