# SPDX-FileCopyrightText: The nomad-semantic-web-service Authors
#
# This file is part of nomad-semantic-web-service.
#
# SPDX-License-Identifier: Apache-2.0
"""Tests for the NXxas auto-conversion of downloaded ESRF .h5 files.

The pure conversion needs pynxtools + the pynxtools-xas reader (the plugin's
`nexus` extra); tests skip cleanly when it isn't installed.
"""

import os.path

import h5py
import pytest

from nomad_semantic_web_service.schema_packages.auto_convert import (
    autoconvert_downloaded_h5,
    convert_h5_bytes_to_nxxas,
)

# Skip the whole module if the reader (nexus extra) isn't available.
pytest.importorskip("pynxtools")
pytest.importorskip("pynxtools_xas")

_H5_FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "data", "esrf_bm23_dac6_10.1.h5"
)


def _read_nxxas_entry(nxs_path):
    with h5py.File(nxs_path, "r") as h5:
        entry_name = next(iter(h5))
        entry = h5[entry_name]
        definition = entry["definition"][()]
        definition = (
            definition.decode() if isinstance(definition, bytes) else definition
        )
        return definition, "energy" in entry, "intensity" in entry


def test_convert_h5_bytes_to_nxxas_produces_valid_nxxas(tmp_path):
    with open(_H5_FIXTURE, "rb") as f:
        h5_bytes = f.read()

    nxs_bytes = convert_h5_bytes_to_nxxas(h5_bytes, nxdl="NXxas_trans", stem="dac6")

    assert nxs_bytes, "conversion produced no output"
    out = tmp_path / "out.nxs"
    out.write_bytes(nxs_bytes)
    definition, has_energy, has_intensity = _read_nxxas_entry(out)
    assert definition == "NXxas_trans"
    assert has_energy and has_intensity


def test_autoconvert_downloaded_h5_writes_and_processes_entry(tmp_path):
    """autoconvert_downloaded_h5 writes each produced .nxs into the upload via
    m_context.raw_file and asks NOMAD to process it. Here m_context is faked
    with a tmp-dir-backed raw_file + a recording process_updated_raw_file, so
    the wiring is exercised without a running NOMAD server."""

    class FakeContext:
        def __init__(self, root):
            self.root = root
            self.processed = []

        def raw_file(self, path, mode="rb"):
            full = self.root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            return open(full, mode)

        def process_updated_raw_file(self, mainfile, allow_modify=False):
            self.processed.append(mainfile)

    class FakeArchive:
        def __init__(self, ctx):
            self.m_context = ctx

    class FakeLogger:
        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

    ctx = FakeContext(tmp_path)
    folder = "dataset-1071092451"
    # seed the downloaded .h5 where autoconvert expects it
    with ctx.raw_file(f"{folder}/DAC6.h5", "wb") as dst, open(_H5_FIXTURE, "rb") as src:
        dst.write(src.read())

    produced = autoconvert_downloaded_h5(
        FakeArchive(ctx), FakeLogger(), folder, ["DAC6.h5"], nxdl="NXxas_trans"
    )

    assert produced == [f"{folder}/DAC6.nxs"]
    assert ctx.processed == [f"{folder}/DAC6.nxs"]
    definition, has_energy, has_intensity = _read_nxxas_entry(
        tmp_path / folder / "DAC6.nxs"
    )
    assert definition == "NXxas_trans"
    assert has_energy and has_intensity
