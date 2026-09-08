import httpx

from nomad_semantic_web_service.catalogue.facilities import (
    FacilityOntology,
    discover_facility_ontologies,
    fetch_facilities,
    find_facility_ontologies,
    ontology_for_concept,
)


def test_finds_facility_ontologies_from_esrf_facilities_payload():
    facilities = [
        {
            "name": "ESRF",
            "ontologies": [
                {
                    "name": "ESRFET",
                    "uri": "https://w3id.org/PaN/ESRFET",
                    "appliesTo": ["technique"],
                }
            ],
        }
    ]

    ontologies = find_facility_ontologies("ESRF", facilities)

    assert ontologies == [
        FacilityOntology(
            name="ESRFET",
            uri="https://w3id.org/PaN/ESRFET",
            applies_to=("technique",),
        )
    ]


def test_find_facility_ontologies_is_case_insensitive_on_facility_name():
    facilities = [{"name": "esrf", "ontologies": []}]
    assert find_facility_ontologies("ESRF", facilities) == []


def test_find_facility_ontologies_missing_facility():
    assert find_facility_ontologies("ESRF", []) == []


def test_find_facility_ontologies_skips_malformed_entries():
    facilities = [
        {
            "name": "ESRF",
            "ontologies": [
                {"name": "ESRFET"},  # missing uri
                {"uri": "https://w3id.org/PaN/ESRFET"},  # missing name
                "not-a-dict",
                {
                    "name": "OWL-Time",
                    "uri": "http://www.w3.org/2006/time",
                    "appliesTo": ["date"],
                },
            ],
        }
    ]

    ontologies = find_facility_ontologies("ESRF", facilities)

    assert ontologies == [
        FacilityOntology(
            name="OWL-Time",
            uri="http://www.w3.org/2006/time",
            applies_to=("date",),
        )
    ]


def test_ontology_for_concept():
    ontologies = [
        FacilityOntology(
            name="ESRFET", uri="https://w3id.org/PaN/ESRFET", applies_to=("technique",)
        ),
        FacilityOntology(
            name="OWL-Time", uri="http://www.w3.org/2006/time", applies_to=("date",)
        ),
    ]

    assert ontology_for_concept(ontologies, "technique").name == "ESRFET"
    assert ontology_for_concept(ontologies, "date").name == "OWL-Time"
    assert ontology_for_concept(ontologies, "sample") is None


def test_fetch_facilities_queries_real_endpoint_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/facilities"
        return httpx.Response(200, json=[{"name": "ESRF", "ontologies": []}])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    facilities = fetch_facilities(client=client)
    assert facilities == [{"name": "ESRF", "ontologies": []}]


def test_fetch_facilities_non_list_payload_returns_empty():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    )
    assert fetch_facilities(client=client) == []


def test_discover_facility_ontologies_combines_fetch_and_find():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "name": "ESRF",
                    "ontologies": [
                        {
                            "name": "ESRFET",
                            "uri": "https://w3id.org/PaN/ESRFET",
                            "appliesTo": ["technique"],
                        }
                    ],
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ontologies = discover_facility_ontologies("ESRF", client=client)
    assert ontologies == [
        FacilityOntology(
            name="ESRFET",
            uri="https://w3id.org/PaN/ESRFET",
            applies_to=("technique",),
        )
    ]
