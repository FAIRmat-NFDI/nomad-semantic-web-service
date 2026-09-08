# Tutorial

This tutorial walks through searching for ESRF datasets via the ELN schema,
including a PANET→ESRFET term mapping.

## 1. Create a search entry

In your NOMAD upload, create a new entry of type **Dataset search request**
(`DatasetSearchRequest`).

## 2. Search directly with an ESRFET term

Fill in:

- `synchrotron`: `ESRF`
- `vocabulary`: `ESRFET`
- `technique_term`: `XAS`
- `start_date` / `end_date`: leave the defaults (`2021-01-01T00:00:00Z` /
  `2022-12-31T23:59:59Z`), or set your own.
- `instrument_name`: `BM23`

Save the entry. `resolved_technique_term` is resolved (shows
`https://w3id.org/PaN/ESRFET#XAS`) and the search runs in the same save:
`matched_datasets` immediately lists the matching demo records — the two
BM23 samples tagged with the XAS technique, `FeK_align` and `DAC6-QMo` — each
with its `investigation_name`/`investigation_title` filled in from the demo
record. (These demo records mirror the shape/values of real ESRF ICAT+ BM23
data; toggle `use_real_icat` in step 4 to hit the live catalogue instead.)

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
`owl:equivalentClass` mapping, stores the result in `resolved_technique_term`,
and searches using it — all in this one save. If no mapping is found,
`mapping_warning` is set instead and `matched_datasets` stays empty.

## 4. Download files from a real dataset

This step needs `use_real_icat: true` (step 2/3 with the local demo data has
no real files behind it). Before downloading, check `ids_status` on the
`MatchedDataset`: real ICAT+ archives older public datasets to tape, and only
`ONLINE` ones download immediately (`require_online: true` on the search
filters out anything else upfront). On an `ONLINE` `MatchedDataset`,
`file_extensions_filter` already defaults to `h5` (clear it for the whole
dataset, or set e.g. `json` instead); click **Download Files** and save. The
files are extracted into your upload under `downloaded_folder` (the zip is
discarded), listed in `downloaded_files` — anonymously, since ICAT+ allows
unauthenticated downloads for public datasets. The same save also creates a
new, standalone **Downloaded dataset** entry in your upload, referencing each
extracted file individually — that entry, not this `MatchedDataset` item, is
the long-term browsable record of the download.

## 5. Query the REST API directly

The same data is reachable without the ELN, for machine clients:

```bash
curl 'http://localhost:8000/nomad-oasis/semantic-web-service/map?term=PaNET01196'

curl 'http://localhost:8000/nomad-oasis/semantic-web-service/ids/data/download?datasetIds=1071092451&fileExtensions=h5' -o dataset.zip
```

See [How to use this plugin](../how_to/use_this_plugin.md) for more routes.
