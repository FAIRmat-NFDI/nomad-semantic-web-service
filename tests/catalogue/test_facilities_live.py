"""Opt-in test against the real icatplus.esrf.fr/facilities, not a mock.

See test_icat_live.py's module docstring for why this suite exists at all.
Excluded by default (see pyproject.toml's `addopts`); run with `pytest -m live`.
"""

import pytest

from nomad_semantic_web_service.catalogue.facilities import (
    discover_facility_ontologies,
    ontology_for_concept,
)

pytestmark = pytest.mark.live


def test_live_esrf_advertises_esrfet_for_technique():
    ontologies = discover_facility_ontologies("ESRF")
    technique_ontology = ontology_for_concept(ontologies, "technique")

    if technique_ontology is None:
        pytest.skip(
            "ESRF's /facilities endpoint advertised nothing for 'technique'; "
            "cannot confirm the expected ESRFET mapping."
        )
    assert technique_ontology.name.upper() == "ESRFET"
