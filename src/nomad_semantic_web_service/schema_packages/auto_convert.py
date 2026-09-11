#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Auto-convert downloaded raw XAS files to NXxas.

When a raw beamline ``.h5`` (e.g. an ESRF transmission-EXAFS scan) is downloaded
into an upload via ``MatchedDataset.trigger_download``, this turns it into a
NeXus ``NXxas`` ``.nxs`` *inside NOMAD*, using the ``pynxtools-xas`` reader, and
registers it as its own entry. The result: ESRF datasets downloaded through the
semantic-web-service ELN become **NXxas entries** — so a single "find everything
with definition NXxas" search finds these.

Design:

* ``convert_h5_bytes_to_nxxas`` is pure and NOMAD-free (tempfile in, bytes out)
  so it can be unit-tested against ``pynxtools-xas`` directly.
* ``autoconvert_downloaded_h5`` does the NOMAD-side wiring (write the ``.nxs``
  into the upload via ``m_context.raw_file`` + ``process_updated_raw_file``),
  mirroring ``downloaded_dataset.write_downloaded_dataset_entry``'s pattern.

Both are defensive: a missing ``pynxtools-xas`` or a conversion failure logs a
warning and skips — it must never break the (already-succeeded) download.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nomad.datamodel.datamodel import EntryArchive
    from structlog.stdlib import BoundLogger

_H5_SUFFIXES = (".h5", ".hdf5")


def convert_h5_bytes_to_nxxas(
    h5_bytes: bytes,
    *,
    nxdl: str = "NXxas",
    stem: str = "dataset",
) -> bytes:
    """Convert raw HDF5 bytes to NXxas ``.nxs`` bytes via the pynxtools-xas reader.

    Pure and NOMAD-independent: writes *h5_bytes* to a temp file, runs the
    pynxtools dataconverter (``reader="xas"``), and returns the resulting
    ``.nxs`` file's bytes. Raises ``ModuleNotFoundError`` if pynxtools isn't
    installed, or the underlying converter's exception on a genuine failure.
    """
    from pynxtools.dataconverter.convert import convert

    with tempfile.TemporaryDirectory() as tmp:
        h5_path = Path(tmp) / f"{stem}{_H5_SUFFIXES[0]}"
        nxs_path = Path(tmp) / f"{stem}.nxs"
        h5_path.write_bytes(h5_bytes)
        convert(
            input_file=(str(h5_path),),
            reader="xas",
            nxdl=nxdl,
            output=str(nxs_path),
            skip_verify=True,
            ignore_undocumented=True,
        )
        return nxs_path.read_bytes()


def autoconvert_downloaded_h5(
    archive: EntryArchive,
    logger: BoundLogger,
    folder: str,
    extracted_files: list[str],
    *,
    nxdl: str = "NXxas",
) -> list[str]:
    """Convert each downloaded ``.h5`` under *folder* to a sibling NXxas ``.nxs``.

    Writes every produced ``.nxs`` into the upload and asks NOMAD to process it
    into its own entry. Returns the list of ``.nxs`` mainfiles created (may be
    empty). Never raises: conversion problems are logged as warnings so the
    download itself is unaffected.
    """
    produced: list[str] = []
    for name in extracted_files:
        if not name.lower().endswith(_H5_SUFFIXES):
            continue
        h5_mainfile = f"{folder}/{name}"
        nxs_mainfile = f"{folder}/{Path(name).stem}.nxs"
        try:
            with archive.m_context.raw_file(h5_mainfile, "rb") as src:
                h5_bytes = src.read()
            nxs_bytes = convert_h5_bytes_to_nxxas(
                h5_bytes, nxdl=nxdl, stem=Path(name).stem
            )
            with archive.m_context.raw_file(nxs_mainfile, "wb") as dst:
                dst.write(nxs_bytes)
            archive.m_context.process_updated_raw_file(nxs_mainfile, allow_modify=True)
            produced.append(nxs_mainfile)
            logger.info("auto-converted to NXxas", h5=h5_mainfile, nxs=nxs_mainfile)
        except ModuleNotFoundError:
            logger.warning(
                "pynxtools-xas not installed; skipping NXxas auto-conversion "
                "of %s. Install it in the deployment to enable Option 2.",
                h5_mainfile,
            )
            return produced
        except Exception:
            logger.warning(
                "NXxas auto-conversion of %s failed; leaving the raw file as-is.",
                h5_mainfile,
                exc_info=True,
            )
    return produced
