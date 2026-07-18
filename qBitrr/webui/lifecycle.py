from __future__ import annotations

import threading
import time

from qBitrr.config_reload_policy import ReloadPlan
from qBitrr.webui.urlbase import _install_url_base_middleware, configured_url_base

# Full-restart keys that only rebuild PlaceHolder workers — Arr search DBs stay on disk.
_PLACEHOLDER_RENAME_FULL_KEYS = frozenset(
    {
        "Settings.FailedCategory",
        "Settings.RecheckCategory",
    }
)


def full_restart_is_placeholder_rename_only(full_restart_keys: list[str]) -> bool:
    """Return True when every full-restart key is a PlaceHolder category rename."""
    if not full_restart_keys:
        return False
    for key in full_restart_keys:
        if not any(
            key.casefold() == member.casefold() for member in _PLACEHOLDER_RENAME_FULL_KEYS
        ):
            return False
    return True


def _config():
    """Return CONFIG from package (patchable via qBitrr.webui.CONFIG)."""
    import qBitrr.webui as webui_mod

    return webui_mod.CONFIG


class LifecycleMixin:
    def _apply_arr_live_refresh(self, plan: ReloadPlan) -> None:
        """Refresh running Arr instances in-place for live-reloadable instance keys."""
        if not hasattr(self.manager, "arr_manager") or not self.manager.arr_manager:
            return
        for instance_name in plan.arr_live_instances:
            for arr in self.manager.arr_manager.managed_objects.values():
                if getattr(arr, "_name", None) != instance_name:
                    continue
                if hasattr(arr, "apply_config_refresh"):
                    arr.apply_config_refresh(preserve_db=True)
                self._reconcile_arr_search_worker(arr)
                break

    def _reconcile_arr_search_worker(self, arr) -> None:
        """Start or stop the Arr search worker to match ``search_missing``.

        LIVE refresh updates attrs on the supervisor Arr object, but the search
        process is only created at spawn time when ``search_missing`` is true.
        This reconciles topology after a WebUI LIVE save without a full Arr respawn.
        """
        search_missing = bool(getattr(arr, "search_missing", False))
        process = getattr(arr, "process_search_loop", None)
        alive = False
        if process is not None:
            try:
                alive = bool(process.is_alive())
            except Exception:
                alive = False
                self.logger.debug(
                    "LIVE search reconcile: is_alive failed for %s",
                    getattr(arr, "_name", ""),
                    exc_info=True,
                )

        if search_missing and alive:
            return

        if process is not None:
            try:
                process.kill()
            except Exception:
                self.logger.debug(
                    "LIVE search reconcile: kill failed for %s",
                    getattr(arr, "_name", ""),
                    exc_info=True,
                )
            try:
                process.terminate()
            except Exception:
                self.logger.debug(
                    "LIVE search reconcile: terminate failed for %s",
                    getattr(arr, "_name", ""),
                    exc_info=True,
                )
            try:
                self.manager.child_processes.remove(process)
            except Exception:
                self.logger.debug(
                    "LIVE search reconcile: child_processes.remove failed for %s",
                    getattr(arr, "_name", ""),
                    exc_info=True,
                )
            registry = getattr(self.manager, "_process_registry", None)
            if isinstance(registry, dict):
                registry.pop(process, None)
            arr.process_search_loop = None

        if not search_missing:
            if process is not None:
                self.logger.info(
                    "Stopped search worker for %s after SearchMissing disabled",
                    getattr(arr, "_name", ""),
                )
            return

        target = getattr(arr, "run_search_loop", None)
        if target is None:
            self.logger.warning(
                "Cannot spawn search worker for %s: run_search_loop missing",
                getattr(arr, "_name", ""),
            )
            return

        import pathos

        new_process = pathos.helpers.mp.Process(target=target, daemon=False)
        arr.process_search_loop = new_process
        self.manager.child_processes.append(new_process)
        if (
            not hasattr(self.manager, "_process_registry")
            or self.manager._process_registry is None
        ):
            self.manager._process_registry = {}
        self.manager._process_registry[new_process] = {
            "category": getattr(arr, "category", ""),
            "name": getattr(arr, "_name", getattr(arr, "category", "")),
            "role": "search",
        }
        try:
            new_process.start()
            self.logger.info(
                "Started search worker for %s after SearchMissing enabled (PID: %s)",
                getattr(arr, "_name", ""),
                getattr(new_process, "pid", None),
            )
        except Exception as exc:
            self.logger.error(
                "Failed to start search worker for %s: %s",
                getattr(arr, "_name", ""),
                exc,
                exc_info=True,
            )
            try:
                self.manager.child_processes.remove(new_process)
            except Exception:
                self.logger.debug(
                    "LIVE search reconcile: cleanup child_processes failed for %s",
                    getattr(arr, "_name", ""),
                    exc_info=True,
                )
            self.manager._process_registry.pop(new_process, None)
            arr.process_search_loop = None

    def _reload_all(self, *, delete_arr_dbs: bool = True):
        # Set rebuilding flag
        self._rebuilding_arrs = True
        try:
            # Stop current processes
            for p in list(self.manager.child_processes):
                try:
                    p.kill()
                except Exception:
                    self.logger.debug("Reload: process kill failed", exc_info=True)
                try:
                    p.terminate()
                except Exception:
                    self.logger.debug("Reload: process terminate failed", exc_info=True)
            self.manager.child_processes.clear()
            self.manager._process_registry.clear()

            # Delete database files for all arr instances before rebuilding
            # (skipped for PlaceHolder-only renames: FailedCategory / RecheckCategory)
            if (
                delete_arr_dbs
                and hasattr(self.manager, "arr_manager")
                and self.manager.arr_manager
            ):
                for arr in self.manager.arr_manager.managed_objects.values():
                    try:
                        if hasattr(arr, "search_db_file") and arr.search_db_file:
                            # Delete main database file
                            if arr.search_db_file.exists():
                                self.logger.info("Deleting database file: %s", arr.search_db_file)
                                arr.search_db_file.unlink()
                                self.logger.success("Deleted database file for %s", arr._name)
                            # Delete WAL file (Write-Ahead Log)
                            wal_file = arr.search_db_file.with_suffix(".db-wal")
                            if wal_file.exists():
                                self.logger.info("Deleting WAL file: %s", wal_file)
                                wal_file.unlink()
                            # Delete SHM file (Shared Memory)
                            shm_file = arr.search_db_file.with_suffix(".db-shm")
                            if shm_file.exists():
                                self.logger.info("Deleting SHM file: %s", shm_file)
                                shm_file.unlink()
                    except Exception as e:
                        self.logger.warning(
                            "Failed to delete database files for %s: %s", arr._name, e
                        )
            elif not delete_arr_dbs:
                self.logger.info(
                    "Preserving Arr search databases during full reload (PlaceHolder rename)"
                )

            # Rebuild arr manager from config and spawn fresh
            from qBitrr.arss import ArrManager

            self.manager.arr_manager = ArrManager(self.manager).build_arr_instances()
            self.manager.configure_auto_update()
            # Spawn and start new processes
            for arr in self.manager.arr_manager.managed_objects.values():
                _, procs = arr.spawn_child_processes()
                for p in procs:
                    try:
                        p.start()
                        self._register_arr_process(arr, p)
                    except Exception:
                        self.logger.debug(
                            "Reload: failed to start process for %s",
                            getattr(arr, "_name", ""),
                            exc_info=True,
                        )

            # Reconcile qBit clients so status/Processes match config after renames
            self.manager.clients.clear()
            self.manager.qbit_versions.clear()
            self.manager.instance_metadata.clear()
            self.manager.instance_health.clear()
            self.manager._initialize_qbit_instances()

            # Rebuild qBit category managers from fresh config
            self.manager.qbit_category_configs.clear()
            self.manager.qbit_category_managers.clear()
            self.manager._reload_qbit_category_configs()
            self.manager._initialize_qbit_category_managers()
            self.manager._spawn_qbit_category_workers()
        finally:
            # Clear rebuilding flag
            self._rebuilding_arrs = False

    def _apply_webui_runtime_settings(self) -> None:
        """Refresh UrlBase middleware and session cookie path from current config."""
        _install_url_base_middleware(self.app)
        url_base = configured_url_base()
        if url_base:
            self.app.config["APPLICATION_ROOT"] = url_base
        else:
            self.app.config.pop("APPLICATION_ROOT", None)
        self.app.config["SESSION_COOKIE_PATH"] = f"{url_base}/" if url_base else "/"

    def _close_waitress_server(self) -> None:
        """Close the active Waitress server handle if present."""
        server = self._server
        if server is None:
            return
        try:
            server.close()
        except Exception as exc:
            self.logger.error(
                "Failed to close WebUI Waitress server during rebind: %s",
                exc,
                exc_info=True,
            )

    def _restart_webui(self):
        """
        Gracefully restart the WebUI server without affecting Arr processes.

        Token and UrlBase soft-apply without rebinding. Host/Port changes close the
        prior Waitress server and start a new one on the updated bind address.
        """
        self.logger.notice("WebUI restart requested (config changed)")

        # Reload config values
        try:
            _config().load()
        except Exception as e:
            self.logger.warning("Failed to reload config: %s", e)

        # Update in-memory values
        new_host = _config().get("WebUI.Host", fallback="0.0.0.0")
        new_port = _config().get("WebUI.Port", fallback=6969)
        new_token = _config().get("WebUI.Token", fallback=None)

        # UrlBase and related settings apply without binding a new port
        self._apply_webui_runtime_settings()

        # Check if restart is actually needed
        needs_restart = new_host != self.host or int(new_port) != int(self.port)

        # Token can be updated without restart
        if new_token != self.token:
            self.token = new_token
            self.logger.info("WebUI token updated")

        if not needs_restart:
            self.logger.info("WebUI Host/Port unchanged, restart not required")
            return

        old_host, old_port = self.host, self.port
        self.host = new_host
        self.port = int(new_port)

        self.logger.info(
            "WebUI rebinding from %s:%s to %s:%s",
            old_host,
            old_port,
            self.host,
            self.port,
        )

        # Own the rebind: signal shutdown, close prior handle, join serve thread, start again.
        # Clear _restart_requested so _serve's finally does not double-start.
        self._restart_requested = False
        self._shutdown_event.set()
        self._close_waitress_server()

        thread = self._thread
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=10)
            if thread.is_alive():
                self.logger.error(
                    "WebUI serve thread did not stop after server close; "
                    "rebind to %s:%s may fail. Restart the qBitrr process to apply Host/Port.",
                    self.host,
                    self.port,
                )

        self._thread = None
        self._server = None

        try:
            self.start()
            self.logger.success("WebUI rebound to %s:%s", self.host, self.port)
        except Exception as exc:
            self.logger.error(
                "WebUI rebind to %s:%s failed: %s. "
                "Restart the qBitrr process to apply Host/Port.",
                self.host,
                self.port,
                exc,
                exc_info=True,
            )

    def _register_arr_process(self, arr, process) -> None:
        """Register an Arr worker process in the manager process registry."""
        if process is None:
            return
        if (
            not hasattr(self.manager, "_process_registry")
            or self.manager._process_registry is None
        ):
            self.manager._process_registry = {}
        role = "search" if getattr(arr, "process_search_loop", None) is process else "torrent"
        self.manager._process_registry[process] = {
            "category": getattr(arr, "category", ""),
            "name": getattr(arr, "_name", getattr(arr, "category", "")),
            "role": role or "worker",
        }

    def _stop_arr_instance(self, arr, category: str, *, delete_db: bool = True):
        """Stop and cleanup a single Arr instance."""
        self.logger.info("Stopping Arr instance: %s", category)

        # Stop processes
        for loop_kind in ("search", "torrent"):
            proc_attr = f"process_{loop_kind}_loop"
            process = getattr(arr, proc_attr, None)
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    self.logger.debug(
                        "Stop instance: process kill failed for %s %s",
                        category,
                        loop_kind,
                        exc_info=True,
                    )
                try:
                    process.terminate()
                except Exception:
                    self.logger.debug(
                        "Stop instance: process terminate failed for %s %s",
                        category,
                        loop_kind,
                        exc_info=True,
                    )
                try:
                    self.manager.child_processes.remove(process)
                except Exception:
                    self.logger.debug(
                        "Stop instance: child_processes.remove failed for %s %s",
                        category,
                        loop_kind,
                        exc_info=True,
                    )
                registry = getattr(self.manager, "_process_registry", None)
                if isinstance(registry, dict):
                    registry.pop(process, None)
                self.logger.debug("Stopped %s process for %s", loop_kind, category)

        # Delete database files (optional — skipped for preserve-db reloads)
        if delete_db:
            try:
                if hasattr(arr, "search_db_file") and arr.search_db_file:
                    if arr.search_db_file.exists():
                        self.logger.info("Deleting database file: %s", arr.search_db_file)
                        arr.search_db_file.unlink()
                        self.logger.success(
                            "Deleted database file for %s", getattr(arr, "_name", category)
                        )
                    # Delete WAL and SHM files
                    for suffix in (".db-wal", ".db-shm"):
                        aux_file = arr.search_db_file.with_suffix(suffix)
                        if aux_file.exists():
                            self.logger.debug("Deleting auxiliary file: %s", aux_file)
                            aux_file.unlink()
            except Exception as e:
                self.logger.warning(
                    "Failed to delete database files for %s: %s",
                    getattr(arr, "_name", category),
                    e,
                )
        else:
            self.logger.info("Preserving search database for %s", getattr(arr, "_name", category))

        # Remove from managed_objects
        self.manager.arr_manager.managed_objects.pop(category, None)
        self.manager.arr_manager.groups.discard(getattr(arr, "_name", ""))
        self.manager.arr_manager.uris.discard(getattr(arr, "uri", ""))
        self.manager.arr_manager.arr_categories.discard(category)

        self.logger.success("Stopped and cleaned up Arr instance: %s", category)

    def _start_arr_instance(self, instance_name: str):
        """Create and start a single Arr instance."""
        self.logger.info("Starting Arr instance: %s", instance_name)

        # Check if instance is managed
        if not _config().get(f"{instance_name}.Managed", fallback=False):
            self.logger.info("Instance %s is not managed, skipping", instance_name)
            return

        try:
            from qBitrr.arss import build_arr_instance
            from qBitrr.errors import SkipException

            new_arr = build_arr_instance(instance_name, self.manager.arr_manager)

            # Register in manager
            self.manager.arr_manager.groups.add(instance_name)
            self.manager.arr_manager.uris.add(new_arr.uri)
            self.manager.arr_manager.managed_objects[new_arr.category] = new_arr
            self.manager.arr_manager.arr_categories.add(new_arr.category)

            # Spawn and start processes
            _, procs = new_arr.spawn_child_processes()
            for p in procs:
                try:
                    p.start()
                    self._register_arr_process(new_arr, p)
                    self.logger.debug("Started process (PID: %s) for %s", p.pid, instance_name)
                except Exception as e:
                    self.logger.error("Failed to start process for %s: %s", instance_name, e)

            self.logger.success(
                "Started Arr instance: %s (category: %s)", instance_name, new_arr.category
            )

        except SkipException:
            self.logger.info("Instance %s skipped (not managed or disabled)", instance_name)
        except Exception as e:
            self.logger.error(
                "Failed to start Arr instance %s: %s", instance_name, e, exc_info=True
            )

    def _reload_arr_instances_ordered(
        self, instance_names: list[str], *, reset_instances: set[str]
    ) -> None:
        """Reload Arr instances, stopping removed names before starting/updating others.

        Rename batches can include both the old (deleted) and new section names. Processing
        deletions first avoids overwriting ``managed_objects[category]`` while old workers
        are still running.
        """
        config_sections = set(_config().sections())
        stops = [name for name in instance_names if name not in config_sections]
        others = [name for name in instance_names if name in config_sections]
        for instance_name in stops + others:
            preserve_db = instance_name not in reset_instances
            self._reload_arr_instance(instance_name, preserve_db=preserve_db)

    def _reload_arr_instance(self, instance_name: str, *, preserve_db: bool = False):
        """Reload a single Arr instance without affecting others."""
        self.logger.notice(
            "Reloading Arr instance: %s (preserve_db=%s)", instance_name, preserve_db
        )

        if not hasattr(self.manager, "arr_manager") or not self.manager.arr_manager:
            self.logger.warning("Cannot reload Arr instance: ArrManager not initialized")
            return

        managed_objects = self.manager.arr_manager.managed_objects

        # Find the instance by name (key is category, so search by _name attribute)
        old_arr = None
        old_category = None
        for category, arr in list(managed_objects.items()):
            if getattr(arr, "_name", None) == instance_name:
                old_arr = arr
                old_category = category
                break

        # Check if instance exists in config
        instance_exists_in_config = instance_name in _config().sections()

        # Handle deletion case
        if not instance_exists_in_config:
            if old_arr:
                self.logger.info("Instance %s removed from config, stopping...", instance_name)
                self._stop_arr_instance(old_arr, old_category, delete_db=not preserve_db)
            else:
                self.logger.debug("Instance %s not found in config or memory", instance_name)
            return

        # Handle update/addition
        if old_arr:
            # Update existing - stop old processes first
            self.logger.info("Updating existing Arr instance: %s", instance_name)
            self._stop_arr_instance(old_arr, old_category, delete_db=not preserve_db)
        else:
            self.logger.info("Adding new Arr instance: %s", instance_name)

        # Small delay to ensure cleanup completes
        time.sleep(0.5)

        # Create new instance
        self._start_arr_instance(instance_name)

        self.logger.success("Successfully reloaded Arr instance: %s", instance_name)
