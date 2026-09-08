# Install This Plugin

## In `nomad-distro-dev`

This plugin already lives at `packages/nomad-semantic-web-service` and is wired
into the workspace:

1. `.gitmodules` has a `packages/nomad-semantic-web-service` submodule entry.
2. The root `pyproject.toml` lists `nomad-semantic-web-service` as a dependency
   and as a `[tool.uv.sources]` workspace member.
3. `nomad.yaml`'s `plugins.entry_points.include` list must contain both entry
   points, since this repo's include list is a non-empty explicit allowlist
   (everything not listed is dormant):

   ```yaml
   plugins:
     entry_points:
       include:
         - "nomad_semantic_web_service.apis:api_entry_point"
         - "nomad_semantic_web_service.schema_packages:schema_package_entry_point"
         - "nomad_semantic_web_service.schema_packages:downloaded_dataset_entry_point"
   ```

4. From the repository root, run `uv sync`, then start NOMAD (`poe start`).

## In another NOMAD Oasis

Read the [NOMAD plugin documentation](https://nomad-lab.eu/prod/v1/staging/docs/plugins/plugins.html#add-a-plugin-to-your-nomad)
for how to add this package as a dependency and enable its entry points in your
own `nomad.yaml`.

## Dependencies

This plugin requires `httpx`, `owlready2`, and `rdflib` for the ICAT+ proxy and
ontology mapping, plus `pyparsing<3` to work around a SPARQL-parsing
incompatibility between `nomad-lab`'s pinned `rdflib==5` and newer `pyparsing`
releases (see [Explanation](../explanation/explanation.md)).

### Optional: `nexus` extra (auto-convert downloaded `.h5` to NXxas)

To enable auto-conversion of downloaded ESRF `.h5` files into NeXus `NXxas`
entries (`MatchedDataset.auto_convert_to_nxxas`), install the `nexus` extra,
which brings `pynxtools-xas`:

```shell
pip install nomad-semantic-web-service[nexus]
```

Without it, downloads still work and only the conversion step is skipped (with a
warning). `pynxtools-xas` must be paired with a `pynxtools` that ships the NXxas
contributed definitions.
