"""Smoke tests for Arr startup after arss.py package split."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from qBitrr.arss import Arr, ArrManager
from qBitrr.errors import SkipException


class TestArssSplitImports(unittest.TestCase):
    """Star-imported names from _shared must be visible in arr submodules."""

    def test_arr_module_exposes_atexit_and_database_error(self) -> None:
        import qBitrr.arss.arr as arr_mod

        self.assertTrue(hasattr(arr_mod, "atexit"))
        self.assertTrue(hasattr(arr_mod, "DatabaseError"))
        self.assertTrue(hasattr(arr_mod, "sync_config_from_disk"))

    def test_atexit_register_works_from_arr_namespace(self) -> None:
        import qBitrr.arss.arr as arr_mod

        session = requests.Session()
        try:
            arr_mod.atexit.register(session.close)
        finally:
            session.close()


class TestArrInitSessionSetup(unittest.TestCase):
    """Arr.__init__ must reach session/atexit setup without NameError."""

    @patch.object(Arr, "register_search_mode")
    @patch("qBitrr.arss.arr.run_logs")
    @patch("qBitrr.arss.arr.CONFIG")
    @patch("qBitrr.arss.arr.QBIT_DISABLED", True)
    @patch("qBitrr.arss.arr.SEARCH_ONLY", True)
    @patch("qBitrr.arss.arr.PROCESS_ONLY", False)
    @patch("qBitrr.arss.arr.TAGLESS", True)
    def test_init_registers_session_close_on_atexit(
        self,
        mock_config: MagicMock,
        _mock_run_logs: MagicMock,
        _mock_register_search: MagicMock,
    ) -> None:
        def config_get(key: str, fallback=None):
            if key.endswith(".Managed"):
                return True
            if "Trackers" in key or key.endswith(".ArrErrorCodesToBlocklist"):
                return []
            if "FileExtensionAllowlist" in key:
                return None
            if "RemoveTrackerWithMessage" in key:
                return []
            if key.endswith(".importMode"):
                return "Auto"
            return fallback

        mock_config.get.side_effect = config_get
        mock_config.get_or_raise.side_effect = lambda key: {
            "TestRadarr.URI": "http://127.0.0.1:7878",
            "TestRadarr.APIKey": "test-key",
        }[key]
        mock_config.get_duration.side_effect = lambda key, fallback=0, unit=None: fallback

        manager = MagicMock(spec=ArrManager)
        manager.groups = set()
        manager.uris = set()
        manager.completed_folders = set()
        manager.category_allowlist = set()
        manager.qbit_manager = MagicMock()
        manager.qbit_manager.logger = MagicMock()
        manager.qbit_manager.logger.level = 20

        mock_client = MagicMock()
        client_builder = MagicMock(return_value=mock_client)

        def _isinstance(obj: object, cls: type) -> bool:
            if obj is mock_client and cls.__name__ == "Radarr":
                return True
            return isinstance(obj, cls)

        with patch("qBitrr.arss.arr.atexit.register") as mock_register:
            with patch("qBitrr.arss.arr.isinstance", side_effect=_isinstance):
                arr = Arr("TestRadarr", manager, client_builder=client_builder)

        self.assertIsInstance(arr.session, requests.Session)
        mock_register.assert_any_call(arr.session.close)


class TestBuildArrInstances(unittest.TestCase):
    """ArrManager.build_arr_instances registers managed Arr objects."""

    @patch("qBitrr.arss.manager.CONFIG")
    @patch("qBitrr.arss.manager.Arr")
    @patch("qBitrr.arss.manager.get_free_space_guard_settings", return_value=("-1", None))
    @patch("qBitrr.arss.manager.get_auto_pause_resume_effective", return_value=False)
    @patch("qBitrr.arss.manager.get_effective_qbit_disabled", return_value=True)
    @patch("qBitrr.arss.manager.qbit_sections", return_value=["qBit"])
    def test_build_arr_instances_populates_managed_objects(
        self,
        _mock_qbit_sections: MagicMock,
        _mock_qbit_disabled: MagicMock,
        _mock_auto_pause: MagicMock,
        _mock_fs: MagicMock,
        mock_arr_cls: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        mock_config.sections.return_value = ["Radarr-1080"]
        mock_arr = MagicMock()
        mock_arr.uri = "http://127.0.0.1:7878"
        mock_arr.category = "radarr1080"
        mock_arr_cls.return_value = mock_arr

        qbit_manager = MagicMock()
        manager = ArrManager(qbit_manager)
        manager.build_arr_instances()

        self.assertIn("radarr1080", manager.managed_objects)
        mock_arr_cls.assert_called_once()

    @patch("qBitrr.arss.manager.CONFIG")
    @patch("qBitrr.arss.manager.get_free_space_guard_settings", return_value=("-1", None))
    @patch("qBitrr.arss.manager.get_auto_pause_resume_effective", return_value=False)
    @patch("qBitrr.arss.manager.get_effective_qbit_disabled", return_value=True)
    @patch("qBitrr.arss.manager.qbit_sections", return_value=[])
    @patch("qBitrr.arss.manager.get_failed_category_effective", return_value="failed")
    @patch("qBitrr.arss.manager.get_recheck_category_effective", return_value="recheck")
    def test_build_arr_instances_skips_unmanaged_sections(
        self,
        _mock_recheck: MagicMock,
        _mock_failed: MagicMock,
        _mock_qbit_sections: MagicMock,
        _mock_qbit_disabled: MagicMock,
        _mock_auto_pause: MagicMock,
        _mock_fs: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        mock_config.sections.return_value = ["Radarr-1080"]
        mock_config.get.return_value = False

        qbit_manager = MagicMock()
        manager = ArrManager(qbit_manager)

        with patch("qBitrr.arss.manager.Arr", side_effect=SkipException):
            manager.build_arr_instances()

        self.assertEqual(manager.groups, set())
        self.assertNotIn("Radarr-1080", manager.managed_objects)
