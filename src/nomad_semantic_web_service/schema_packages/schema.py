from typing import TYPE_CHECKING

from nomad.config import config
from nomad.datamodel.data import ArchiveSection, Schema, UseCaseElnCategory
from nomad.datamodel.metainfo.annotations import ELNAnnotation, ELNComponentEnum
from nomad.metainfo import Datetime, MEnum, Quantity, SchemaPackage
from nomad.metainfo.metainfo import Section, SubSection

from nomad_semantic_web_service.catalogue.facilities import (
    discover_facility_ontologies,
    ontology_for_concept,
)
from nomad_semantic_web_service.catalogue.icat import (
    DatasetNotOnlineError,
    download_datafiles,
    fetch_icat_catalogue_datasets,
    get_datasets_status,
    landing_page_for_dataset,
)
from nomad_semantic_web_service.catalogue.search import (
    investigation_field,
    resolve_technique_term,
    search_local_datasets,
    technique_pids_of,
)
from nomad_semantic_web_service.schema_packages.auto_convert import (
    autoconvert_downloaded_h5,
)
from nomad_semantic_web_service.schema_packages.downloaded_dataset import (
    DownloadedDatasetFields,
    write_downloaded_dataset_entry,
)

if TYPE_CHECKING:
    from nomad.datamodel.datamodel import EntryArchive
    from structlog.stdlib import BoundLogger

configuration = config.get_plugin_entry_point(
    "nomad_semantic_web_service.schema_packages:schema_package_entry_point"
)

m_package = SchemaPackage()


class MatchedDataset(ArchiveSection):
    m_def = Section(label="Matched dataset")

    dataset_id = Quantity(type=int, description="The catalogue-internal dataset id.")
    name = Quantity(type=str, description="Dataset title.")
    start_date = Quantity(type=Datetime, description="Start date-time of the dataset.")
    end_date = Quantity(type=Datetime, description="End date-time of the dataset.")
    instrument_name = Quantity(
        type=str, description="Name of the beamline or instrument."
    )
    technique_pids = Quantity(
        type=str,
        description=(
            "Comma-separated ESRFET technique IRIs associated with the dataset."
        ),
    )
    sample_name = Quantity(type=str, description="Name/description of the sample.")
    investigation_name = Quantity(
        type=str,
        description=(
            "Name (proposal/experiment session id) of the ICAT+ investigation "
            "this dataset belongs to."
        ),
    )
    investigation_title = Quantity(
        type=str,
        description="Title of the ICAT+ investigation this dataset belongs to.",
    )
    landing_page = Quantity(
        type=str,
        description=(
            "DOI-based landing page for the dataset (https://doi.org/<doi>), "
            "resolved from the dataset record."
        ),
    )
    ids_status = Quantity(
        type=str,
        description=(
            "IDS online/archive status ('ONLINE', 'ARCHIVED', 'RESTORING', "
            "...), refreshed on every search against real ICAT+ (None for "
            "local demo data, which has no real IDS-backed status). Only "
            "'ONLINE' datasets download immediately - ICAT+ archives older "
            "public datasets to tape, and restoring an archived one can take "
            "minutes to hours; trigger_download requests a restore and "
            "reports the status instead of failing outright."
        ),
    )
    file_extensions_filter = Quantity(
        type=str,
        default="h5",
        description=(
            'Comma-separated file extensions to download, e.g. "h5,edf". Leave '
            "empty to download the whole dataset (can be much larger)."
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.StringEditQuantity),
    )
    trigger_download = Quantity(
        type=bool,
        default=False,
        description=(
            "Downloads this dataset (filtered by file_extensions_filter, if "
            "set) from ICAT+ and extracts it into this upload, under "
            "downloaded_folder. ICAT+ issues an anonymous session for public "
            "datasets, so no credentials are needed; only works against the "
            "real ICAT+ endpoint (use_real_icat), not the local demo data, "
            "which has no real files behind it. If the dataset is archived "
            "(ids_status != 'ONLINE'), this requests a restore and updates "
            "ids_status instead of downloading - retry once it reports "
            "'ONLINE', which for tape-archived data can take a while."
        ),
        a_eln=ELNAnnotation(
            component=ELNComponentEnum.ActionEditQuantity, label="Download Files"
        ),
    )
    downloaded_folder = Quantity(
        type=str,
        description="Path (within this upload) where the downloaded dataset files were extracted.",
    )
    downloaded_files = Quantity(
        type=str,
        description="Comma-separated names of the extracted files, relative to downloaded_folder.",
    )
    auto_convert_to_nxxas = Quantity(
        type=bool,
        default=True,
        description=(
            "After downloading, convert each raw .h5 to a NeXus NXxas .nxs with "
            "pynxtools-xas and register it as its own entry (OSCARS Option 2). "
            "This makes ESRF datasets downloaded here discoverable by a "
            "'definition == NXxas' search, and directly. Needs pynxtools-xas installed "
            "in the deployment; if absent, conversion is skipped with a warning."
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.BoolEditQuantity),
    )
    converted_nxs_files = Quantity(
        type=str,
        description="Comma-separated NXxas .nxs mainfiles produced by auto-conversion.",
    )

    def normalize(self, archive: "EntryArchive", logger: "BoundLogger") -> None:
        super().normalize(archive, logger)

        if not self.trigger_download:
            return

        from nomad.datamodel.context import ServerContext

        if not isinstance(archive.m_context, ServerContext):
            # Skip the outbound download in offline/test contexts.
            self.trigger_download = False
            return

        try:
            extensions = (
                [
                    ext.strip()
                    for ext in self.file_extensions_filter.split(",")
                    if ext.strip()
                ]
                if self.file_extensions_filter
                else None
            )
            members = download_datafiles(self.dataset_id, file_extensions=extensions)
            folder = f"dataset-{self.dataset_id}"
            archive.m_context.upload_files.raw_create_directory(folder)

            extracted = []
            for member_name, data in members:
                member_dir = "/".join(member_name.split("/")[:-1])
                if member_dir:
                    archive.m_context.upload_files.raw_create_directory(
                        f"{folder}/{member_dir}"
                    )
                with archive.m_context.raw_file(f"{folder}/{member_name}", "wb") as dst:
                    dst.write(data)
                extracted.append(member_name)

            self.downloaded_folder = folder
            self.downloaded_files = ", ".join(extracted)

            write_downloaded_dataset_entry(
                archive,
                logger,
                DownloadedDatasetFields(
                    dataset_id=self.dataset_id,
                    name=self.name,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    instrument_name=self.instrument_name,
                    technique_pids=self.technique_pids,
                    sample_name=self.sample_name,
                    investigation_name=self.investigation_name,
                    investigation_title=self.investigation_title,
                    landing_page=self.landing_page,
                    ids_status=self.ids_status,
                ),
                downloaded_folder=folder,
                extracted_files=extracted,
            )

            if self.auto_convert_to_nxxas:
                produced = autoconvert_downloaded_h5(archive, logger, folder, extracted)
                self.converted_nxs_files = ", ".join(produced) or None
        except DatasetNotOnlineError as exc:
            # Expected, not a bug: real ICAT+ archives older public datasets
            # to tape. A restore was already requested inside
            # download_dataset_archive() - record the status so the GUI
            # explains why nothing downloaded instead of a bare failure.
            self.ids_status = exc.status
            logger.warning(str(exc))
        except Exception:
            # A warning, not an error: this is an external-dependency failure
            # (ICAT+ unreachable/down), not a defect in this entry's own data,
            # and logger.error() would mark the entry with a processing error
            # in the GUI for what may just be a transient outage.
            logger.warning("Dataset download failed.", exc_info=True)
        finally:
            self.trigger_download = False


class DatasetSearchRequest(Schema):
    """
    A structured search request for ESRF-style public dataset catalogues,
    modeled after the oscarsSemanticWebService CLI's interactive prompts.
    """

    m_def = Section(label="Dataset search request", categories=[UseCaseElnCategory])

    synchrotron = Quantity(
        type=MEnum("ESRF", "Diamond Light Source", "MAX IV"),
        default="ESRF",
        description=(
            "Synchrotron to search. Only ESRF is currently wired to a live "
            "catalogue endpoint; the others are placeholders."
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.EnumEditQuantity),
    )
    vocabulary = Quantity(
        type=MEnum("ESRFET", "PANET"),
        default="ESRFET",
        description=(
            "Vocabulary used for technique_term. ESRFET terms are used directly; "
            "PANET terms are first mapped to an equivalent ESRFET term via the "
            "local ontology before searching."
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.RadioEnumEditQuantity),
    )
    technique_term = Quantity(
        type=str,
        default="XAS",
        description=(
            "Technique term, IRI, or compact curie. For vocabulary=ESRFET, e.g. "
            '"XAS" or "ESRFET:XAS". For vocabulary=PANET, e.g. "PaNET01196" or '
            '"PaNET:PaNET01196". Defaults to XAS, the OSCARS demonstrator target.'
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.StringEditQuantity),
    )
    start_date = Quantity(
        type=Datetime,
        default="2021-01-01T00:00:00+00:00",
        description="Start date-time of the search window.",
        a_eln=ELNAnnotation(component=ELNComponentEnum.DateTimeEditQuantity),
    )
    end_date = Quantity(
        type=Datetime,
        default="2022-12-31T23:59:59+00:00",
        description="End date-time of the search window.",
        a_eln=ELNAnnotation(component=ELNComponentEnum.DateTimeEditQuantity),
    )
    instrument_name = Quantity(
        type=str,
        default="ID21",
        description=(
            "Beamline or instrument name to filter by. Defaults to ID21, whose "
            "public datasets are annotated with the XAS technique and kept on "
            "disk (the OSCARS demonstrator source; ESRF's tape-archived EXAFS "
            "beamlines are not reliably restorable on demand)."
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.StringEditQuantity),
    )
    use_real_icat = Quantity(
        type=bool,
        default=True,
        description=(
            "If set, search the real ESRF ICAT+ public datasets endpoint instead "
            "of the local demo data. Requires network access to icatplus.esrf.fr. "
            "Defaults to True for the OSCARS demonstrator; set False to explore "
            "against the bundled demo catalogue offline."
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.BoolEditQuantity),
    )
    require_online = Quantity(
        type=bool,
        default=False,
        description=(
            "Only applies when use_real_icat=True. ICAT+'s /catalogue/datasets "
            "search has no server-side online/archived filter (checked against "
            "its own API contract), so this filters matched_datasets "
            "client-side after the fact, dropping any real-ICAT+ match that "
            "isn't currently 'ONLINE' in IDS - i.e. tape-archived datasets "
            "that would need a slow restore (see MatchedDataset.ids_status/ "
            "trigger_download) before download works. Restoring one doesn't "
            "retroactively resurface it here; search again once it reports "
            "'ONLINE'. If the IDS status lookup itself fails, this is skipped "
            "(fails open) so a transient status-check outage doesn't silently "
            "empty out matched_datasets."
        ),
        a_eln=ELNAnnotation(component=ELNComponentEnum.BoolEditQuantity),
    )

    resolved_technique_term = Quantity(
        type=str,
        description=(
            "The ESRFET IRI actually used for the search, after PANET->ESRFET "
            "mapping if vocabulary=PANET."
        ),
    )
    mapping_warning = Quantity(
        type=str,
        description="Set if a PANET->ESRFET mapping could not be resolved.",
    )
    detected_technique_ontology = Quantity(
        type=str,
        description=(
            "Name of the ontology the synchrotron's /facilities endpoint "
            "advertises for technique terms (e.g. 'ESRFET'), discovered "
            "automatically from live facility metadata. None if discovery "
            "hasn't run yet (non-ESRF synchrotron, offline/test context) or the "
            "facility advertised nothing for the 'technique' concept."
        ),
    )
    vocabulary_warning = Quantity(
        type=str,
        description=(
            "Set if detected_technique_ontology disagrees with the manually "
            "selected vocabulary. This only flags the mismatch - vocabulary is "
            "never overridden automatically, so a real discovery result always "
            "yields to the user's own selection."
        ),
    )
    search_key = Quantity(
        type=str,
        description=(
            "Internal cache key of the last completed search (date window, "
            "resolved term, instrument, use_real_icat, require_online). Used "
            "to avoid re-running the search, and discarding any in-progress "
            "downloads on matched_datasets items, on every save when the "
            "search inputs haven't actually changed."
        ),
    )
    matched_datasets = SubSection(section_def=MatchedDataset, repeats=True)

    def normalize(self, archive: "EntryArchive", logger: "BoundLogger") -> None:
        super().normalize(archive, logger)

        self.mapping_warning = None
        self.detected_technique_ontology = None
        self.vocabulary_warning = None

        # Quantity defaults are returned as the raw literal (e.g. a str) until
        # explicitly assigned, which is what triggers the Datetime type's
        # coercion to a real datetime. Re-assigning forces that coercion even
        # when start_date/end_date were never set and are still at default.
        self.start_date = self.start_date
        self.end_date = self.end_date

        if self.synchrotron != "ESRF":
            logger.warning(f"{self.synchrotron} is not wired to a live endpoint yet.")
            return

        from nomad.datamodel.context import ServerContext

        if isinstance(archive.m_context, ServerContext):
            self._detect_technique_vocabulary(logger)

        if not self.technique_term:
            return

        resolved = resolve_technique_term(self.technique_term, self.vocabulary)
        if resolved["resolved_iri"] is None:
            self.mapping_warning = resolved["warning"]
            return
        self.resolved_technique_term = resolved["resolved_iri"]

        key = "|".join(
            str(part)
            for part in (
                self.start_date,
                self.end_date,
                self.resolved_technique_term,
                self.instrument_name,
                self.use_real_icat,
                self.require_online,
            )
        )
        if key == self.search_key and self.matched_datasets:
            # Search inputs haven't changed since the last run: skip re-running
            # so that in-progress trigger_download/file_extensions_filter state
            # on existing matched_datasets items isn't discarded on every save.
            return
        self.search_key = key

        self._run_search(archive, logger)

    def _detect_technique_vocabulary(self, logger: "BoundLogger") -> None:
        try:
            ontologies = discover_facility_ontologies(self.synchrotron)
            technique_ontology = ontology_for_concept(ontologies, "technique")
        except Exception:
            # A warning, not an error: see the matching note on the ICAT+
            # calls below - this is an external-dependency failure, not a
            # defect in this entry's own data.
            logger.warning("Facility ontology discovery failed.", exc_info=True)
            return

        if not technique_ontology:
            return

        self.detected_technique_ontology = technique_ontology.name
        detected_vocabulary = (
            "ESRFET" if technique_ontology.name.upper() == "ESRFET" else "PANET"
        )
        if detected_vocabulary != self.vocabulary:
            self.vocabulary_warning = (
                f"{self.synchrotron}'s /facilities endpoint advertises "
                f"{technique_ontology.name} for technique terms, but "
                f"vocabulary is set to {self.vocabulary}; technique_term may "
                "be interpreted in the wrong vocabulary."
            )

    def _run_search(self, archive: "EntryArchive", logger: "BoundLogger") -> None:
        from nomad.datamodel.context import ServerContext

        if self.use_real_icat and not isinstance(archive.m_context, ServerContext):
            # Skip the outbound ICAT+ call in offline/test contexts.
            return

        try:
            if self.use_real_icat:
                raw = fetch_icat_catalogue_datasets(
                    start_date=self.start_date,
                    end_date=self.end_date,
                    instrument_name=self.instrument_name,
                    technique_pids=self.resolved_technique_term,
                )
            else:
                raw = search_local_datasets(
                    self.start_date,
                    self.end_date,
                    self.resolved_technique_term,
                    self.instrument_name,
                )
        except Exception:
            # A warning, not an error: see the matching note in
            # MatchedDataset.normalize() above.
            logger.warning("Catalogue search failed.", exc_info=True)
            return

        if not isinstance(raw, list):
            logger.warning("Catalogue search returned an unexpected response shape.")
            return

        ids_statuses: dict[int, str] = {}
        ids_status_lookup_failed = False
        if self.use_real_icat and raw:
            try:
                dataset_ids = [
                    dataset["id"]
                    for dataset in raw
                    if isinstance(dataset, dict) and dataset.get("id") is not None
                ]
                ids_statuses = get_datasets_status(dataset_ids)
            except Exception:
                # A warning, not an error: see the matching note in
                # MatchedDataset.normalize() above. matched_datasets is still
                # useful without ids_status, so this doesn't abort the search.
                ids_status_lookup_failed = True
                logger.warning(
                    "Could not fetch IDS online/archive status.", exc_info=True
                )

        if self.use_real_icat and self.require_online and not ids_status_lookup_failed:
            raw = [
                dataset
                for dataset in raw
                if isinstance(dataset, dict)
                and ids_statuses.get(dataset.get("id")) == "ONLINE"
            ]

        self.matched_datasets = [
            MatchedDataset(
                dataset_id=dataset.get("id"),
                name=dataset.get("name"),
                start_date=dataset.get("startDate"),
                end_date=dataset.get("endDate"),
                instrument_name=dataset.get("instrumentName"),
                technique_pids=", ".join(technique_pids_of(dataset)),
                sample_name=dataset.get("sampleName"),
                investigation_name=investigation_field(dataset, "name"),
                investigation_title=investigation_field(dataset, "title"),
                landing_page=landing_page_for_dataset(dataset),
                ids_status=ids_statuses.get(dataset.get("id")),
            )
            for dataset in raw
            if isinstance(dataset, dict)
        ]


m_package.__init_metainfo__()
