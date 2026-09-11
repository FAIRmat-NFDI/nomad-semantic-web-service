# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
from nomad.config.models.plugins import APIEntryPoint


class SemanticWebServiceAPIEntryPoint(APIEntryPoint):
    def load(self):
        from nomad_semantic_web_service.apis.api import app

        return app


api_entry_point = SemanticWebServiceAPIEntryPoint(
    prefix="semantic-web-service",
    name="SemanticWebServiceAPI",
    description=(
        "ESRF-style public dataset catalogue endpoint with PANET/ESRFET "
        "semantic OpenAPI annotations."
    ),
)
