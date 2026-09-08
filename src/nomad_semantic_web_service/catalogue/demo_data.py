from datetime import datetime, timezone
from typing import Any

# Offline demonstrator / test fixture, shaped and valued like real ESRF ICAT+
# `/catalogue/datasets` records (see https://icatplus.esrf.fr/swagger.json,
# schema `dataset`): BM23 (ESRF's EXAFS beamline) transmission-XAS acquisitions
# belonging to an `investigation` (proposal/experiment session) with an ESRF
# DOI, `techniques` as a list of {..., "pid": str} objects, and `sampleName`.
# `investigation.doi` (not the internal `location` path) is the public landing
# page, resolved by catalogue.icat.landing_page_for_dataset.
#
# NOTE ON `techniques`: real *public* ESRF records currently often come back with an
# empty `techniques: []` (they aren't annotated yet). These fixtures are annotated
# with the XAS/EXAFS technique PIDs they *should* carry, so the offline flow can
# exercise technique-based discovery (the intended behaviour once ESRF annotates).
# Dates sit in 2021-2022 to match DatasetSearchRequest's default search window so
# the demo finds them out of the box.
_ESRF = "https://w3id.org/PaN/ESRFET#"


def _technique(dataset_id: int, tid: int, label: str) -> dict[str, Any]:
    return {"id": tid, "datasetId": dataset_id, "pid": _ESRF + label, "name": label}


# Each record belongs to its own investigation (proposal/experiment session),
# as on real ICAT+ where different datasets come from different beamtimes.
FAKE_DATASETS: list[dict[str, Any]] = [
    {
        "id": 1001,
        "name": "0001",
        "startDate": datetime(2021, 3, 18, 9, 15, tzinfo=timezone.utc),
        "endDate": datetime(2021, 3, 18, 11, 45, tzinfo=timezone.utc),
        "location": "/data/visitor/ihhc3846/bm23/20210318/raw/FeK_align",
        "investigation": {
            "name": "IH-HC-3846",
            "title": "High pressure EXAFS study on FeTiO3",
            "doi": "10.15151/ESRF-ES-1042671535",
        },
        "instrumentName": "BM23",
        "sampleName": "FeK_align",
        "techniques": [_technique(1001, 1, "XAS")],
    },
    {
        "id": 1002,
        "name": "ambient",
        "startDate": datetime(2021, 6, 19, 14, 0, tzinfo=timezone.utc),
        "endDate": datetime(2021, 6, 19, 18, 30, tzinfo=timezone.utc),
        "location": "/data/visitor/ma5321/bm23/20210619/raw/DAC6-QMo",
        "investigation": {
            "name": "MA-5321",
            "title": "Operando XAS of Mo-based catalysts under pressure",
            "doi": "10.15151/ESRF-ES-1058872210",
        },
        "instrumentName": "BM23",
        "sampleName": "DAC6-QMo",
        "techniques": [_technique(1002, 2, "EXAFS"), _technique(1002, 3, "XAS")],
    },
    {
        "id": 1003,
        "name": "0001",
        "startDate": datetime(2022, 2, 10, 8, 30, tzinfo=timezone.utc),
        "endDate": datetime(2022, 2, 10, 15, 10, tzinfo=timezone.utc),
        "location": "/data/visitor/es987/bm23/20220210/raw/Brucite",
        "investigation": {
            "name": "ES-987",
            "title": "EXAFS of brucite-type layered hydroxides",
            "doi": "10.15151/ESRF-ES-0993217744",
        },
        "instrumentName": "BM23",
        "sampleName": "Brucite",
        # EXAFS but not tagged with the generic XAS PID -> not a "XAS" match,
        # mirroring how sibling scans in a session can carry different tags.
        "techniques": [_technique(1003, 4, "EXAFS")],
    },
    {
        "id": 1004,
        "name": "align",
        "startDate": datetime(2022, 9, 12, 7, 45, tzinfo=timezone.utc),
        "endDate": datetime(2022, 9, 12, 12, 20, tzinfo=timezone.utc),
        "location": "/data/inhouse/ch6120/bm23/20220912/raw/beam_align",
        "investigation": {
            "name": "CH-6120",
            "title": "Beamline alignment and energy calibration",
            "doi": "10.15151/ESRF-ES-0771145509",
        },
        "instrumentName": "BM23",
        "sampleName": "beam alignment",
        "techniques": [],
    },
]
