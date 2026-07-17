from __future__ import annotations

import time

from qBitrr.config_reload_policy import ReloadPlan
from qBitrr.webui.urlbase import _install_url_base_middleware, configured_url_base


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
                break

    def _reload_all(self):
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
            if hasattr(self.manager, "arr_manager") and self.manager.arr_manager:
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
                    except Exception:
                        self.logger.debug(
                            "Reload: failed to start process for %s",
                            getattr(arr, "_name", ""),
                            exc_info=True,
                        )

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

    def _restart_webui(self):
        """
        Gracefully restart the WebUI server without affecting Arr processes.
        This is used when WebUI.Host, WebUI.Port, or WebUI.Token changes.
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
        needs_restart = new_host != self.host or new_port != self.port

        # Token can be updated without restart
        if new_token != self.token:
            self.token = new_token
            self.logger.info("WebUI token updated")

        if not needs_restart:
            self.logger.info("WebUI Host/Port unchanged, restart not required")
            return

        # Update host/port
        self.host = new_host
        self.port = new_port

        # Signal restart
        self._restart_requested = True
        self._shutdown_event.set()

        self.logger.info("WebUI will restart on %s:%s", self.host, self.port)

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
