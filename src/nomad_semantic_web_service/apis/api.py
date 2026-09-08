from __future__ import annotations

from datetime import date
from typing import Annotated, Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.openapi.utils import get_openapi
from nomad.config import config
from pydantic import BaseModel, ConfigDict, Field

from nomad_semantic_web_service.catalogue.icat import (
    ICAT_DATASETS_URL,
    download_dataset_archive,
    fetch_icat_catalogue_datasets,
)
from nomad_semantic_web_service.catalogue.ontology import query_panet_to_esrfet

ESRFET = "https://w3id.org/PaN/ESRFET#"
ESRFET_PURL = "http://purl.org/pan-science/ESRFET#"
PANET = "http://purl.org/pan-science/PaNET/"
OWL_TIME = "http://www.w3.org/2006/time#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
DCAT = "http://www.w3.org/ns/dcat#"
DCTERMS = "http://purl.org/dc/terms/"
SCHEMA = "https://schema.org/"


class MappingResult(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "x-semantic-type": OWL + "Class",
            "x-semantic-relation": OWL + "equivalentClass",
        }
    )

    sourceTerm: str = Field(
        examples=["http://purl.org/pan-science/PaNET/PaNET01196"],
        json_schema_extra={"x-semantic-type": PANET + "PaNETConcept"},
    )
    sourceCompact: str = Field(examples=["PaNET:PaNET01196"])
    targetTerm: str = Field(
        examples=["http://purl.org/pan-science/ESRFET#XAS"],
        json_schema_extra={"x-semantic-type": ESRFET_PURL + "experimental_technique"},
    )
    targetCompact: str = Field(examples=["ESRFET:XAS"])
    targetLabel: str = Field(examples=["XAS"])
    relation: str = Field(
        examples=["owl:equivalentClass"],
        json_schema_extra={"x-semantic-type": OWL + "equivalentClass"},
    )


class MappingResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "x-semantic-type": "https://schema.org/DefinedTermSet",
            "x-source-ontology": PANET.rstrip("/"),
            "x-target-ontology": ESRFET_PURL.rstrip("#"),
        }
    )

    source: str = Field(examples=["PANET"])
    target: str = Field(examples=["ESRFET"])
    term: str = Field(examples=["http://purl.org/pan-science/PaNET/PaNET01196"])
    targetTerm: str | None = Field(
        default=None,
        examples=["https://w3id.org/PaN/ESRFET#XAS"],
        json_schema_extra={"x-semantic-type": ESRFET_PURL + "experimental_technique"},
    )
    mappings: list[MappingResult]


api_entry_point = config.get_plugin_entry_point(
    "nomad_semantic_web_service.apis:api_entry_point"
)

app = FastAPI(
    root_path=f"{config.services.api_base_path}/{api_entry_point.prefix}",
    title="Semantic Web Service",
    description=(
        "Demonstrator for an ESRF-style catalogue endpoint enriched "
        "with semantic OpenAPI annotations."
    ),
)


@app.get(
    "/catalogue/datasets",
    response_model=None,
    tags=["Catalogue"],
    summary="List public datasets from the real ESRF ICAT+ catalogue",
    description=(
        "Proxies the real ESRF ICAT+ `GET /catalogue/datasets` route (the only "
        "catalogue-listing path that exists on icatplus.esrf.fr), forwarding "
        "`startDate`, `endDate`, and `instrumentName`. Anonymous — public "
        "datasets need no credentials.\n\n"
        "ICAT+ documents a `techniquePids` filter on this route and applies it "
        "server-side, so it is forwarded when given. Note it only matches "
        "datasets annotated with technique PIDs; public records currently "
        "mostly carry an empty `techniques[]`, so a technique filter returns "
        "nothing for them and callers narrow by beamline instead."
    ),
    operation_id="get_catalogue_datasets",
)
def get_catalogue_datasets(
    startDate: Annotated[
        date,
        Query(
            description="Start date forwarded to ICAT+ in YYYY-MM-DD format.",
            examples=["2023-02-09"],
        ),
    ],
    endDate: Annotated[
        date,
        Query(
            description="End date forwarded to ICAT+ in YYYY-MM-DD format.",
            examples=["2023-02-13"],
        ),
    ],
    instrumentName: Annotated[
        str | None,
        Query(
            description="Beamline or instrument name forwarded to ICAT+.",
            examples=["BM23"],
        ),
    ] = None,
    techniquePids: Annotated[
        str | None,
        Query(
            description=(
                "Technique PID(s) forwarded to ICAT+'s server-side "
                "`techniquePids` filter. Only matches datasets annotated with "
                "technique PIDs (public BM23 data currently has none)."
            ),
            examples=["https://w3id.org/PaN/ESRFET#XAS"],
        ),
    ] = None,
) -> Any:
    try:
        return fetch_icat_catalogue_datasets(
            start_date=startDate,
            end_date=endDate,
            instrument_name=instrumentName,
            technique_pids=techniquePids,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={"upstream": ICAT_DATASETS_URL, "message": exc.response.text},
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={"upstream": ICAT_DATASETS_URL, "message": str(exc)},
        ) from exc


@app.get(
    "/ids/data/download",
    tags=["Catalogue"],
    summary="Download a public dataset as a zip archive",
    description=(
        "Proxies the real ESRF IDS `GET /ids/data/download` route (which exists "
        "on icatplus.esrf.fr), downloading a dataset anonymously as a zip. "
        "ICAT+ issues an anonymous session for public datasets; no credentials "
        "needed. Optionally filter to only files with the given extensions "
        "(e.g. 'h5,edf') — done by listing the dataset's files first and "
        "downloading only the matching ones, since IDS itself has no "
        "format parameter."
    ),
    operation_id="download_dataset",
)
def download_dataset(
    datasetIds: Annotated[
        int,
        Query(
            description="ICAT+ dataset id to download.",
            examples=[1071092451],
        ),
    ],
    fileExtensions: Annotated[
        str | None,
        Query(
            description="Comma-separated file extensions to include, e.g. 'h5,edf'. Omit to download the whole dataset.",
            examples=["h5,edf"],
        ),
    ] = None,
) -> Response:
    extensions = (
        [ext.strip() for ext in fileExtensions.split(",") if ext.strip()]
        if fileExtensions
        else None
    )
    try:
        content = download_dataset_archive(datasetIds, file_extensions=extensions)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=str(exc)
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="dataset-{datasetIds}.zip"'
        },
    )


@app.get(
    "/map",
    response_model=MappingResponse,
    tags=["Ontology Mapping"],
    summary="Map a PANET term to ESRFET",
    description=(
        "Queries the local ESRFET ontology for owl:equivalentClass mappings "
        "from a PANET term to ESRFET terms."
    ),
    operation_id="map_panet_to_esrfet",
)
def map_panet_to_esrfet(
    term: Annotated[
        str,
        Query(
            description="PANET term IRI, compact term, or local identifier.",
            examples=[
                "http://purl.org/pan-science/PaNET/PaNET01196",
                "PaNET:PaNET01196",
                "PaNET01196",
            ],
        ),
    ],
    source: Annotated[
        str,
        Query(
            description="Source ontology. The current demonstrator supports PANET.",
            examples=["PANET"],
        ),
    ] = "PANET",
    target: Annotated[
        str,
        Query(
            description="Target ontology. The current demonstrator supports ESRFET.",
            examples=["ESRFET"],
        ),
    ] = "ESRFET",
) -> MappingResponse:
    mappings = []
    if source.upper() == "PANET" and target.upper() == "ESRFET":
        mappings = [MappingResult(**mapping) for mapping in query_panet_to_esrfet(term)]

    return MappingResponse(
        source=source.upper(),
        target=target.upper(),
        term=term,
        targetTerm=mappings[0].targetTerm if mappings else None,
        mappings=mappings,
    )


@app.get("/health", tags=["Service"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}


def add_semantic_annotations(openapi_schema: dict) -> dict:
    openapi_schema["x-supported-ontologies"] = {
        "ESRFET": ESRFET.rstrip("#"),
        "ESRFET-PURL": ESRFET_PURL.rstrip("#"),
        "PaNET": PANET.rstrip("/"),
        "OWL": OWL.rstrip("#"),
        "OWL-Time": OWL_TIME.rstrip("#"),
        "XSD": XSD.rstrip("#"),
        "DCAT": DCAT.rstrip("#"),
        "Dublin Core Terms": DCTERMS.rstrip("/"),
        "schema.org": SCHEMA.rstrip("/"),
    }

    operation = openapi_schema["paths"]["/catalogue/datasets"]["get"]
    operation["x-semantic-operation"] = {
        "type": DCAT + "DataService",
        "upstream": ICAT_DATASETS_URL,
        "returns": DCAT + "Dataset",
        "supportedOntologies": ["ESRFET", "OWL-Time", "XSD", "DCAT", "schema.org"],
    }
    operation["x-jsonld-context"] = {
        "dcat": DCAT,
        "dcterms": DCTERMS,
        "schema": SCHEMA,
        "esrfet": ESRFET,
        "time": OWL_TIME,
        "xsd": XSD,
    }

    parameter_annotations = {
        "startDate": {
            "x-semantic-type": OWL_TIME + "Instant",
            "x-datatype": XSD + "date",
            "x-jsonld-property": SCHEMA + "startDate",
        },
        "endDate": {
            "x-semantic-type": OWL_TIME + "Instant",
            "x-datatype": XSD + "date",
            "x-jsonld-property": SCHEMA + "endDate",
        },
        "techniquePids": {
            "x-semantic-type": ESRFET + "experimental_technique",
            "x-ontology": ESRFET.rstrip("#"),
            "x-value-kind": "comma-separated-iri-list",
            "x-jsonld-property": ESRFET + "usesTechnique",
        },
        "instrumentName": {
            "x-semantic-type": SCHEMA + "instrument",
            "x-jsonld-property": SCHEMA + "instrument",
        },
    }

    for parameter in operation.get("parameters", []):
        parameter.update(parameter_annotations.get(parameter["name"], {}))

    mapping_operation = openapi_schema["paths"]["/map"]["get"]
    mapping_operation["x-semantic-operation"] = {
        "type": "https://schema.org/Action",
        "sourceOntology": PANET.rstrip("/"),
        "targetOntology": ESRFET_PURL.rstrip("#"),
        "mappingPredicate": OWL + "equivalentClass",
        "queryEngine": "OWL/XML ontology loaded with owlready2 and queried as RDF with SPARQL",
    }
    mapping_parameter_annotations = {
        "term": {
            "x-semantic-type": PANET + "PaNETConcept",
            "x-ontology": PANET.rstrip("/"),
            "x-value-kind": "iri-or-curie",
            "x-query-role": "source ontology term",
        },
        "source": {
            "x-semantic-type": "https://schema.org/DefinedTermSet",
            "x-default-ontology": PANET.rstrip("/"),
        },
        "target": {
            "x-semantic-type": "https://schema.org/DefinedTermSet",
            "x-default-ontology": ESRFET_PURL.rstrip("#"),
        },
    }
    for parameter in mapping_operation.get("parameters", []):
        parameter.update(mapping_parameter_annotations.get(parameter["name"], {}))

    return openapi_schema


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = add_semantic_annotations(openapi_schema)
    return app.openapi_schema


app.openapi = custom_openapi
