# Welcome to the `nomad-semantic-web-service` documentation

A NOMAD plugin that finds and extracts public synchrotron dataset records from
ESRF-style catalogues, with semantic OpenAPI annotations and PANET/ESRFET
ontology term mapping.

## Introduction

This plugin brings the [`oscarsSemanticWebService`](https://github.com/gkoum/oscarsSemanticWebService)
proof-of-concept by Giannis Koumoutsos into NOMAD as two cooperating entry points:

- A mounted REST API that mirrors the real ESRF ICAT+ paths — `/catalogue/datasets`
  (dataset listing), `/ids/data/download` (anonymous zip download), plus `/map`
  (PANET→ESRFET mapping) and `/health` — for machine clients, with `x-*`
  semantic annotations on its OpenAPI contract.
- An ELN schema, `DatasetSearchRequest`, that lets a user describe a catalogue
  search (synchrotron, technique term, date range, instrument) as a NOMAD entry;
  saving the entry runs the search and stores the matched datasets back into it.
  Each matched dataset can then be downloaded — anonymously, optionally
  filtered by file extension — via a "Download Files" action, and (with the
  `nexus` extra installed) each downloaded raw `.h5` is auto-converted to a
  NeXus `NXxas` entry.

Both share the same underlying domain logic (`catalogue/icat.py`,
`catalogue/ontology.py`, `catalogue/search.py`), which has no FastAPI dependency
and is called directly by each entry point — never over HTTP loopback.

<div markdown="block" class="home-grid">
<div markdown="block">

### Tutorial

- [Tutorial](tutorial/tutorial.md)

</div>
<div markdown="block">

### How-to guides

How-to guides provide step-by-step instructions for a wide range of tasks, with the overarching topics:

- [Install this plugin](how_to/install_this_plugin.md)
- [Use this plugin](how_to/use_this_plugin.md)
- [Contribute to this plugin](how_to/contribute_to_this_plugin.md)
- [Contribute to the documentation](how_to/contribute_to_the_documentation.md)

</div>

<div markdown="block">

### Explanation

The explanation [section](explanation/explanation.md) provides background knowledge on this plugin.

</div>
<div markdown="block">

### Reference

The reference [section](reference/references.md) includes the REST API routes,
the `DatasetSearchRequest` ELN schema fields, and the relevant configuration options.

</div>
</div>
