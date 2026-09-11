# Tutorial

This tutorial walks through searching for ESRF datasets via the ELN schema,
including a PANET→ESRFET term mapping.

## 1. Create a search entry

In your NOMAD upload, create a new entry of type **Dataset search request**
(`DatasetSearchRequest`).

## 2. Search with the defaults (offline demo)

The entry's defaults already describe the OSCARS demonstrator's ID21 XAS search,
so you can just save it. The relevant fields are:

- `synchrotron`: `ESRF`
- `vocabulary`: `ESRFET`
- `technique_term`: `XAS`
- `instrument_name`: `ID21`
- `start_date` / `end_date`: `2021-01-01T00:00:00Z` / `2022-12-31T23:59:59Z`
- `use_real_icat`: `false`

With `use_real_icat` off (the default), saving searches the bundled **offline
demo catalogue** (no network needed). `resolved_technique_term` is resolved
(shows `https://w3id.org/PaN/ESRFET#XAS`) and the search runs in the same save:
`matched_datasets` lists the two ID21 demo records tagged with the XAS technique,
`FeK_align` and `DAC6-QMo`, each with its `investigation_name`/`investigation_title`
filled in. The demo records (`catalogue/demo_data.py`) mirror the shape and
values of real ESRF ICAT+ records; step 4 runs the same search against the live
catalogue.

If `synchrotron` is `ESRF`, saving also queries ESRF's own `/facilities`
endpoint to check which vocabulary it actually advertises for technique
terms, filling in `detected_technique_ontology`. This is informational only:
it never changes your `vocabulary` selection, but if the two disagree,
`vocabulary_warning` explains the mismatch.

## 3. Search with a PANET term instead

Create a second entry, this time with:

- `vocabulary`: `PANET`
- `technique_term`: `PaNET01196`

Save: the plugin looks up the PANET term in the local ESRFET ontology, finds its
`owl:equivalentClass` mapping (by walking rdflib triples directly, not via a
SPARQL query), stores the result in `resolved_technique_term`, and searches
using it — all in this one save. If no mapping is found, `mapping_warning` is set
instead and `matched_datasets` stays empty.

## 4. Search the live ESRF ICAT+ catalogue

Set `use_real_icat`: `true` to run the same search against the real endpoint
(needs network access to `icatplus.esrf.fr` and a server context). ID21's public
XAS datasets *are* annotated with the XAS technique PID, so the resolved IRI is
forwarded to ICAT+'s server-side `techniquePids` filter, and `matched_datasets`
lists the real ID21 XAS datasets in the window — newest first — each with its
`investigation_name`/`investigation_title`, DOI-based `landing_page`, and IDS
`ids_status` filled in. (BM23, ESRF's tape-archived EXAFS beamline, is *not*
annotated: a `techniquePids` filter returns nothing for it, which is why the
demonstrator uses ID21.)

## 5. Download files from a real dataset

This step needs `use_real_icat: true` (step 4); the offline demo catalogue has no
real files behind it. Before downloading, check `ids_status` on the
`MatchedDataset`: real ICAT+ archives older public datasets to tape, and only
`ONLINE` ones download immediately (`require_online: true` on the search
filters out anything else upfront). On an `ONLINE` `MatchedDataset`,
`file_extensions_filter` already defaults to `h5` (clear it for the whole
dataset, or set e.g. `json` instead); click **Download Files** and save. The
files are extracted into your upload under `downloaded_folder`, listed in
`downloaded_files` — anonymously, since ICAT+ allows unauthenticated downloads
for public datasets. IDS returns a zip when several files are requested but the
raw file itself when exactly one datafile matches (e.g. a single-`.h5` ID21
dataset); either way the extracted files land in `downloaded_folder`. The same
save also creates a new, standalone **Downloaded dataset** entry in your upload,
referencing each extracted file individually — that entry, not this
`MatchedDataset` item, is the long-term browsable record of the download. If the
`nexus` extra (`pynxtools-xas`) is installed and `auto_convert_to_nxxas` is left
on, each downloaded raw `.h5` is also converted to a NeXus `NXxas` `.nxs` entry.

## 6. Query the REST API directly

The same data is reachable without the ELN, for machine clients:

```bash
curl 'http://localhost:8000/nomad-oasis/semantic-web-service/map?term=PaNET01196'

# A single-.h5 ID21 dataset comes back as the raw file, not a zip.
curl 'http://localhost:8000/nomad-oasis/semantic-web-service/ids/data/download?datasetIds=874478618&fileExtensions=h5' -o dataset_or_file.bin
```

See [How to > Use this plugin](../how_to/use_this_plugin.md) for more routes.
