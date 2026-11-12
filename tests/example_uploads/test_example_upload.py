# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
"""Test the OSCARS XAS demonstrator example upload entry point."""

from pathlib import Path

import nomad_semantic_web_service


def test_importing_example_upload():
    # raises if pydantic validation on the ExampleUploadEntryPoint fails
    from nomad_semantic_web_service.example_uploads import (
        oscars_xas_demo_example_upload,
    )

    assert oscars_xas_demo_example_upload.title == "OSCARS XAS Demonstrator"
    assert oscars_xas_demo_example_upload.category == "OSCARS Demonstrators"


def test_example_upload_resources_exist():
    from nomad_semantic_web_service.example_uploads import (
        oscars_xas_demo_example_upload,
    )

    package_root = Path(nomad_semantic_web_service.__file__).parent
    resource = oscars_xas_demo_example_upload.resources[0]
    bundle = package_root / Path(resource.path).parent

    assert bundle.is_dir()
    for name in (
        "1_full_pipeline.ipynb",
        "2_eln_esrf_plus_bessy.ipynb",
        "oscars_demo.py",
        "run_workflow.py",
        "README.md",
        "nomad.json",
    ):
        assert (bundle / name).is_file(), name
