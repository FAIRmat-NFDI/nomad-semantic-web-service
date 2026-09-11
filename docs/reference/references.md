# References

## REST API routes

Mounted under `{api_base_path}/semantic-web-service`.

The routes mirror the real ESRF ICAT+ paths and proxy them anonymously (there
is no separate "local demo" HTTP route — the demo `FAKE_DATASETS` are reached
only through the ELN with `use_real_icat=False`).

| Route | Method | Description |
|---|---|---|
| `/catalogue/datasets` | GET | Proxy the real ESRF ICAT+ `/catalogue/datasets` listing (`startDate`, `endDate`, `instrumentName`, and `techniquePids` — forwarded to ICAT+'s server-side technique filter). Raw JSON from ICAT+. |
| `/ids/data/download` | GET | Proxy the real ESRF IDS `/ids/data/download`: download a dataset (`datasetIds`) as a zip, anonymously. Optional `fileExtensions` (comma-separated, e.g. `h5,edf`) restricts to matching files. 404 if a filter matches nothing. |
| `/map` | GET | Map a PANET term to its equivalent ESRFET term(s) via the local ontology. |
| `/health` | GET | Health check. |

## `DatasetSearchRequest` ELN schema fields

| Field | Type | Editable | Description |
|---|---|---|---|
| `synchrotron` | enum (`ESRF`, `Diamond Light Source`, `MAX IV`) | Yes | Only `ESRF` is wired to a live endpoint. |
| `vocabulary` | enum (`ESRFET`, `PANET`) | Yes | Vocabulary used for `technique_term`. |
| `technique_term` | string | Yes | Term, IRI, or compact curie in the selected vocabulary. Default `XAS`. |
| `start_date` / `end_date` | datetime | Yes | Search window. Default `2021-01-01T00:00:00Z`/`2022-12-31T23:59:59Z`. |
| `instrument_name` | string | Yes | Beamline/instrument filter. Default `ID21` (its public XAS datasets are technique-annotated and on disk). |
| `use_real_icat` | bool | Yes | Search the real ICAT+ endpoint instead of the local demo data. Default `False` (offline demo); set `True` for live ESRF ICAT+. Real-ICAT results are returned newest-first. |
| `require_online` | bool | Yes | Only applies with `use_real_icat=True`. ICAT+'s `/catalogue/datasets` search has no server-side online/archived filter, so this filters `matched_datasets` client-side after the fact, dropping any match whose `ids_status` isn't `ONLINE` (tape-archived data that would need a slow restore first). Fails open (keeps everything) if the IDS status lookup itself errors. |
| `resolved_technique_term` | string | No | The ESRFET IRI actually used for the search, resolved automatically on every save. |
| `mapping_warning` | string | No | Set if a PANET→ESRFET mapping could not be resolved. |
| `detected_technique_ontology` | string | No | Name of the ontology `synchrotron`'s `/facilities` endpoint advertises for technique terms (e.g. `ESRFET`), discovered automatically. `None` if discovery hasn't run (non-`ESRF` synchrotron, offline/test context) or nothing was advertised for the `technique` concept. |
| `vocabulary_warning` | string | No | Set if `detected_technique_ontology` disagrees with the manually selected `vocabulary`. Informational only — `vocabulary` is never overridden automatically. |
| `search_key` | string | No | Internal cache key of the last completed search (date window, resolved term, instrument, `use_real_icat`, `require_online`). Search only re-runs when this changes, so that saving for an unrelated reason (e.g. setting `file_extensions_filter` on a `matched_datasets` item) doesn't rebuild `matched_datasets` and discard that item's state. |
| `matched_datasets` | repeated section | No | Matching dataset records, populated automatically once `technique_term`/dates are set — see `MatchedDataset` fields below. |

## `MatchedDataset` fields (items of `matched_datasets`)

| Field | Type | Editable | Description |
|---|---|---|---|
| `dataset_id`, `name`, `start_date`, `end_date`, `instrument_name`, `sample_name` | various | No | Mirror the underlying dataset record. |
| `technique_pids` | string | No | Comma-separated ESRFET technique IRIs. |
| `investigation_name` | string | No | Name (proposal/experiment session id) of the ICAT+ investigation this dataset belongs to, if present on the record. |
| `investigation_title` | string | No | Title of that investigation, if present on the record. |
| `landing_page` | string | No | DOI-based link (`https://doi.org/<doi>`), if the dataset record has one. |
| `ids_status` | string | No | IDS online/archive status (`ONLINE`, `ARCHIVED`, `RESTORING`, ...) for real-ICAT+ matches, refreshed on every search. `None` for local demo data. Only `ONLINE` downloads immediately. |
| `file_extensions_filter` | string | Yes | Comma-separated file extensions, e.g. `h5,edf`. Defaults to `h5`; clear it to download the whole dataset (can be much larger). |
| `trigger_download` (action button "Download Files") | bool | Yes (action) | Anonymously downloads this dataset (filtered by `file_extensions_filter`, if set) from ICAT+, extracts it into the upload under `downloaded_folder`, and discards the zip. Only works against real ICAT+ data (`use_real_icat=True`); a no-op for local demo data, which has no real files behind it. On success, also creates a standalone `DownloadedDataset` entry (see below) referencing the extracted files. Resets to `False` once the download runs. |
| `downloaded_folder` | string | No | Path (within the upload) where the downloaded dataset files were extracted, once `trigger_download` has run. |
| `downloaded_files` | string | No | Comma-separated names of the extracted files, relative to `downloaded_folder`. |
| `auto_convert_to_nxxas` | bool | Yes | After downloading, convert each raw `.h5` to a NeXus `NXxas` `.nxs` (via `pynxtools-xas`) and register it as its own entry, so ESRF downloads become discoverable by the same `definition == NXxas` search as native NeXus data. Default `True`. Needs the `nexus` extra (`pynxtools-xas`) installed; without it the step is skipped with a warning and the download is unaffected. |
| `converted_nxs_files` | string | No | Comma-separated `.nxs` mainfiles produced by the auto-conversion. |

## `DownloadedDataset` entry (created automatically by `trigger_download`)

A standalone entry, separate from `DatasetSearchRequest`, created once per successful `trigger_download` (as `<downloaded_folder>.archive.yaml`, e.g. `dataset-874478618.archive.yaml`) so a downloaded dataset is independently browsable/searchable rather than buried inside a `matched_datasets` item.

| Field | Type | Description |
|---|---|---|
| `dataset_id`, `name`, `start_date`, `end_date`, `instrument_name`, `sample_name` | various | Mirror the `MatchedDataset` this entry was created from. |
| `technique_pids`, `investigation_name`, `investigation_title`, `landing_page` | string | Same as on `MatchedDataset`. |
| `ids_status` | string | The IDS status (`ONLINE`, ...) at the time of download. |
| `downloaded_folder` | string | Path (within the upload) the files were extracted into. |
| `files` | repeated section | One `DownloadedFile` item (`path`, a `FileEditQuantity`) per extracted file, browsable/clickable in the GUI. |

## Configuration

All entry points are registered under `[project.entry-points.'nomad.plugin']`
in `pyproject.toml`:

- `nomad_semantic_web_service.apis:api_entry_point`
- `nomad_semantic_web_service.schema_packages:schema_package_entry_point`
- `nomad_semantic_web_service.schema_packages:downloaded_dataset_entry_point`

They must also be listed in the consuming NOMAD instance's `nomad.yaml` under
`plugins.entry_points.include` if that list is a non-empty explicit allowlist.
