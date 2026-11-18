# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
"""Entry point for the OSCARS XAS demonstrator example upload."""

from nomad.config.models.plugins import ExampleUploadEntryPoint

oscars_xas_demo_example_upload = ExampleUploadEntryPoint(
    title="OSCARS XAS Demonstrator",
    category="OSCARS Demonstrators",
    description="""
        Find public X-ray absorption spectroscopy (XAS) data at two synchrotron
        facilities through their own discovery mechanisms &mdash; ESRF via this
        plugin's ICAT+ catalogue search (semantic PaNET&rarr;ESRFET mapping,
        anonymous download) and BESSY II via the NOMAD search API &mdash;
        standardize both to the NeXus `NXxas` application definition with
        [`pynxtools-xas`](https://github.com/FAIRmat-NFDI/pynxtools-xas), run the
        ewoks/est EXAFS workflow, and write the results back as NOMAD entries.
        Runs from two Jupyter notebooks in NORTH.
    """,
    resources=["example_uploads/oscars_xas_demo/*"],
)
