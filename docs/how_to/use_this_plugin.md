# How to Use This Plugin

This plugin can be used in a NOMAD Oasis installation.

## Add This Plugin to Your NOMAD installation

Read the [NOMAD plugin documentation](https://nomad-lab.eu/prod/v1/staging/docs/plugins/plugins.html#add-a-plugin-to-your-nomad) for all details on how to deploy the plugin on your NOMAD instance.

## Using the REST API

The API is mounted at `{api_base_path}/semantic-web-service` (in this repo's dev
setup, `http://localhost:8000/nomad-oasis/semantic-web-service`):

The routes mirror the real ESRF ICAT+ paths (`/catalogue/datasets`,
`/ids/data/download`) and proxy them anonymously:

```bash
curl 'http://localhost:8000/nomad-oasis/semantic-web-service/health'

# List real ESRF datasets by date + beamline (proxies ICAT+ /catalogue/datasets).
# techniquePids is forwarded too, but public BM23 data isn't annotated yet, so
# it returns nothing — narrow by beamline instead (see ESRF_ICAT notes).
curl 'http://localhost:8000/nomad-oasis/semantic-web-service/catalogue/datasets?startDate=2023-02-09&endDate=2023-02-13&instrumentName=BM23'

curl 'http://localhost:8000/nomad-oasis/semantic-web-service/map?term=PaNET01196&source=PANET&target=ESRFET'

# Download a real public dataset anonymously, optionally filtered by file extension:
curl 'http://localhost:8000/nomad-oasis/semantic-web-service/ids/data/download?datasetIds=1071092451&fileExtensions=h5' -o dataset.zip
```

See the [reference](../reference/references.md) for all routes, or open
`.../semantic-web-service/docs` for the interactive Swagger UI.

## Using the ELN schema

1. In the NOMAD GUI, create a new entry of type **Dataset search request**.
2. Fill in `synchrotron` (only `ESRF` is currently wired to a live endpoint),
   `vocabulary` (`ESRFET` or `PANET`), `technique_term`, `start_date`, `end_date`,
   and optionally `instrument_name`.
3. Save the entry. `resolved_technique_term` is resolved (after PANET→ESRFET
   mapping, if applicable) and the search runs automatically in the same save —
   `matched_datasets` is populated immediately, including a DOI-based
   `landing_page` and `investigation_name`/`investigation_title` where
   available. Editing the search fields and saving again re-runs the search;
   saving for an unrelated reason (e.g. step 4 below) does not, so it won't
   discard work in progress on `matched_datasets` items. For `ESRF`, the same
   save also checks the facility's advertised technique vocabulary
   (`detected_technique_ontology`) and flags a `vocabulary_warning` if it
   disagrees with your `vocabulary` selection, without changing it.
4. Toggle `use_real_icat` to query the real ESRF ICAT+ endpoint instead of the
   local demo data (requires network access to `icatplus.esrf.fr`). Each real
   match's `ids_status` (`ONLINE`/`ARCHIVED`/`RESTORING`/...) is filled in at
   the same time — real ICAT+ archives older public datasets to tape, and
   only `ONLINE` ones download immediately. Toggle `require_online` to drop
   non-`ONLINE` matches from `matched_datasets` entirely instead of just
   flagging them.
5. To download a matched dataset's files: open it in `matched_datasets`,
   optionally adjust `file_extensions_filter` (defaults to `h5`; clear it to
   get the whole dataset), then click the **Download Files** action button
   and save. The files are extracted into the upload under `downloaded_folder`
   (e.g. `dataset-874478618/`), listed in `downloaded_files`; the zip itself is
   discarded. This only works for real ICAT+ results (step 4) — the local
   demo data has no real files behind it. If the dataset isn't `ONLINE`, a
   restore is requested and `ids_status` is updated instead of downloading —
   tape restores can take minutes to hours, so retry later.
6. A successful download also creates a new, standalone **Downloaded dataset**
   entry (`dataset-874478618.archive.yaml`) in the same upload, independent of
   the `DatasetSearchRequest` entry — visible in the upload's entry list, with
   each downloaded file individually browsable under `files`.
7. If the `nexus` extra is installed (`pip install nomad-semantic-web-service[nexus]`,
   which brings `pynxtools-xas`) and `auto_convert_to_nxxas` is left on (the
   default), each downloaded raw `.h5` is also converted to a NeXus `NXxas`
   `.nxs` beside it and processed into its own **XAS** entry — so the ESRF
   dataset becomes discoverable by the same `definition == NXxas` search used
   for already-NeXus data. Without the extra, this step is skipped with a
   warning and the download itself is unaffected.
