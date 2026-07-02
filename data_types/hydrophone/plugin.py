"""Hydrophone data_type — complex data, viewed PER INSTRUMENT.

Discovery + archive-file availability come from the shared ComplexInstrumentPlugin
base. Categories and expected file extensions are configured in
``config/data_types.yaml``.
"""

from __future__ import annotations

from data_types.complex_base import ComplexInstrumentPlugin


class HydrophonePlugin(ComplexInstrumentPlugin):
    data_type = "hydrophone"
