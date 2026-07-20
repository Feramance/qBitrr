"""Compatibility shim: prefer ArrBase / RadarrArr / SonarrArr / LidarrArr.

``Arr`` is an alias of :class:`ArrBase` for tests and legacy imports. Do **not**
construct ``Arr`` for real workers — type-specific methods (``_db_update_media``,
``_db_update_single_entry``, ``_maybe_do_search_impl``, ``_get_models``) raise on
the base class. Use :func:`qBitrr.arss.factory.build_arr_instance` instead.
"""

from qBitrr.arss.arr_base import ArrBase

# Short alias for tests and call sites that still import ``Arr``.
Arr = ArrBase

__all__ = ["Arr", "ArrBase"]
