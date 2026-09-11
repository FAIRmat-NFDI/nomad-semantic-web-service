# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0

from nomad.config.models.plugins import SchemaPackageEntryPoint


class DatasetSearchEntryPoint(SchemaPackageEntryPoint):
    def load(self):
        from nomad_semantic_web_service.schema_packages.schema import m_package

        return m_package


schema_package_entry_point = DatasetSearchEntryPoint(
    name="DatasetSearchSchemaPackage",
    description=("ELN schema for ESRF-style public dataset catalogue search requests."),
)


class DownloadedDatasetEntryPoint(SchemaPackageEntryPoint):
    def load(self):
        from nomad_semantic_web_service.schema_packages.downloaded_dataset import (
            m_package,
        )

        return m_package


downloaded_dataset_entry_point = DownloadedDatasetEntryPoint(
    name="DownloadedDatasetSchemaPackage",
    description=(
        "ELN schema for datasets downloaded from a public synchrotron catalogue, "
        "created automatically by DatasetSearchRequest's trigger_download."
    ),
)
