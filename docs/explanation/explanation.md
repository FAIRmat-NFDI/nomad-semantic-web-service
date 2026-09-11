# Explanation

Background and design rationale for the plugin. For exact routes, schema fields,
and configuration see the [Reference](../reference/references.md); this page is
about *what* the plugin does and *why* it is built the way it is.

## Provenance

The plugin is built on top of
[`oscarsSemanticWebService`](https://github.com/gkoum/oscarsSemanticWebService),
a FastAPI proof-of-concept by Giannis Koumoutsos for an ESRF-style catalogue
endpoint with semantic OpenAPI annotations. Its catalogue routes, PANET/ESRFET
ontology mapping, and facility technique-vocabulary discovery were brought into
NOMAD and additionally exposed as an ELN schema. The plugin tracks the upstream
POC's ongoing development.

## Architecture

Three layers, following the repository's "schemas ≠ runtime logic" principle:

| Layer | Package | Depends on FastAPI? |
|---|---|---|
| Domain logic (ICAT+ access, ontology mapping, search, facility discovery) | `catalogue/` | No |
| REST API (semantically-annotated proxy of the real ICAT+ paths) | `apis/` | Yes |
| ELN schema (`DatasetSearchRequest` and its results) | `schema_packages/` | No |

The domain layer has no web-framework dependency, so both the REST API and the
ELN call the same plain Python functions directly — never over an HTTP loopback.
The REST layer deliberately mirrors the **real** ESRF ICAT+ paths
(`/catalogue/datasets`, `/ids/data/download`) so it is a faithful semantic proxy
rather than an invented parallel API.

## What a search does

A `DatasetSearchRequest` describes a catalogue search (synchrotron, technique
term, date range, instrument). Saving it runs the search and writes the matches
back into the same entry — there is no separate "run" button. Two ingredients
are worth understanding:

- **The semantic step.** A technique term is resolved to an ESRFET IRI: a PANET
  term is mapped through the local `ESRFET.owl` ontology via its
  `owl:equivalentClass` relations, an ESRFET term is normalised directly. This
  resolved IRI is what the search and the annotated API expose as the
  "findable-via-semantics" result. (Two ESRFET namespaces exist — the published
  `w3id.org` form used on dataset records and the `purl.org` form used inside
  the ontology — and the plugin converts between them so a mapping result can be
  matched against records.) The mapping walks rdflib triples directly rather
  than issuing a SPARQL query — see the note on `pyparsing` below.
- **Real vs. offline.** By default the search runs against a local demo fixture
  (ID21 XAS records shaped to match the default instrument/technique/dates);
  turn `use_real_icat` on (and only in a server context) to query the live ESRF
  ICAT+ instead. The offline fixture mirrors the real
  `techniques`/`investigation`/DOI record structure, so no code needs to branch
  on which source it came from.

## Technique filtering, server-side

The live `/catalogue/datasets` route accepts a server-side `techniquePids`
filter, and the plugin forwards the resolved ESRFET IRI. This is what makes the
demonstrator target **ID21**: its public XAS datasets *are* annotated with the
technique PID, so the resolved `ESRFET#XAS` IRI filters them server-side. Not all
beamlines are annotated — public BM23 records, for instance, carry an empty
`techniques` list and would need narrowing by beamline instead. Results are
returned newest-first, so the first match uses the current export convention.
(See the demonstrator's `ESRF_ICAT.md` for the empirical write-up.)

## Anonymous, format-filtered download — and the tape problem

Public ESRF datasets download **without authentication**: ICAT+ issues an
anonymous session and the IDS backend serves the files. Downloads can be
restricted to specific file extensions (default `h5`), since whole datasets can
be far larger than the handful of files actually needed. IDS returns a zip when
several files are requested but the **raw file itself** when exactly one
datafile matches (e.g. a single-`.h5` ID21 dataset); the plugin detects the zip
magic bytes and handles both.

Public data more than a few years past embargo is often migrated to **tape**.
Such a dataset can't be downloaded immediately — it must be restored first, and
that restore is asynchronous and can take minutes to hours. The plugin does not
try to wait it out inside a request: it checks online/archived status up front,
requests a restore when needed, surfaces the status on each match, and can
optionally drop archived matches from the results. This is realistic FAIR-data
friction, so it is treated as information for the user, not as an error.

## Downloaded data becomes its own entry, and optionally an NXxas entry

When a matched dataset is downloaded, its files are extracted into the upload
(the zip is discarded) so they are individually browsable, and a standalone
**Downloaded dataset** entry is created to record the download independently of
the search entry that happened to find it. (Creating an entry from inside
another entry's normalization is done by writing a raw mainfile and asking NOMAD
to process it — the same pattern NOMAD's own built-in "downloads" section uses.)

If the optional `nexus` extra (`pynxtools-xas`) is installed, a further step
converts each downloaded raw `.h5` into a NeXus **NXxas** `.nxs` and processes
it into its own entry. The point is a uniform discovery *mechanism*: an ESRF
dataset pulled in this way then answers the same `definition == NXxas` search as
data that arrived already in NeXus form (e.g. on a BESSY oasis). The conversion
core is a pure bytes-in/bytes-out function (so it is unit-testable on its own),
and the whole step is best-effort — if the extra is absent or a file won't
convert, it is skipped with a warning and the download itself is unaffected.

## Smaller design decisions worth knowing

- **Failures from external services are warnings, not errors.** An ICAT+ outage
  is not a defect in the entry's own data, and NOMAD flags `logger.error()` calls
  as processing errors in the GUI — so outbound-call failures are logged as
  warnings instead.
- **The search caches its inputs.** Because the search re-runs on every save, a
  fingerprint of the search inputs guards it, so saving for an unrelated reason
  (e.g. starting a download on a match) doesn't rebuild the results list and
  discard in-progress state.
- **Facility discovery informs but never overrides.** The plugin asks ESRF which
  vocabulary it advertises for techniques and records it, but never rewrites the
  user's manual `vocabulary` choice — a mismatch only raises a warning.
- **No `pyparsing` pin; the ontology mapping avoids SPARQL.** `nomad-lab`'s
  environment resolves `pyparsing>=3` (matplotlib requires it), and `rdflib` 5's
  SPARQL parser breaks under `pyparsing>=3`. Rather than pin `pyparsing<3` (which
  would make the plugin un-installable alongside `nomad-lab` in a NOMAD Oasis),
  the PANET→ESRFET mapping navigates rdflib triples (`graph.objects`/`subjects`
  over `owl:equivalentClass`) directly, which has no SPARQL/`pyparsing`
  dependency.
