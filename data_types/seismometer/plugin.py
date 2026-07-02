"""Seismometer data_type — complex data, viewed PER INSTRUMENT."""

from __future__ import annotations

from data_types.complex_base import ComplexInstrumentPlugin


class SeismometerPlugin(ComplexInstrumentPlugin):
    data_type = "seismometer"
