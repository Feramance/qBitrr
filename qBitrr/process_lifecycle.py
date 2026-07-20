"""Process spawn/restart lifecycle helpers for qBitManager."""

from __future__ import annotations

import contextlib
import time

import pathos


class ProcessLifecycle:
    def _enqueue_failed_spawn(self, arr, role: str) -> None:
        """Track a failed worker spawn and queue it for periodic retry."""
        category = getattr(arr, "category", "")
        key = (category, role)
        self._failed_spawn_attempts[key] = self._failed_spawn_attempts.get(key, 0) + 1
        meta = {"category": category, "role": role, "name": getattr(arr, "_name", "")}
        already_pending = any(
            m.get("category") == category and m.get("role") == role
            for _, m in self._pending_spawns
        )
        if not already_pending:
            self._pending_spawns.append((arr, meta))

    def _discard_unstarted_spawn(self, proc) -> None:
        """Remove a failed or never-started worker from supervisor tracking."""
        self._process_registry.pop(proc, None)
        with contextlib.suppress(ValueError):
            self.child_processes.remove(proc)

    def _should_restart_process(self, category: str, role: str) -> bool:
        """
        Determine if a process should be restarted based on restart count and window.

        Tracks restart attempts per (category, role) combination and prevents
        crash loops by enforcing maximum restart limits within a time window.

        Args:
            category: The Arr category (e.g., "radarr", "sonarr")
            role: The process role ("search" or "torrent")

        Returns:
            bool: True if process should be restarted, False otherwise
        """
        key = (category, role)
        now = time.time()

        # Get restart history for this process type
        if key not in self._process_restart_counts:
            self._process_restart_counts[key] = []

        restart_times = self._process_restart_counts[key]

        # Remove timestamps outside the restart window
        restart_times[:] = [t for t in restart_times if now - t < self.process_restart_window]

        # Check if we've exceeded max restarts
        if len(restart_times) >= self.max_process_restarts:
            self.logger.error(
                "Process %s/%s has failed %d times in %d seconds. Auto-restart disabled for this process.",
                category,
                role,
                len(restart_times),
                self.process_restart_window,
            )
            return False

        return True

    def _restart_process(
        self, failed_proc: pathos.helpers.mp.Process, meta: dict[str, str]
    ) -> bool:
        """
        Restart a failed worker process.

        Creates a new process instance with the same target function, starts it,
        and updates all tracking structures to reference the new process.

        Args:
            failed_proc: The failed process object
            meta: Process metadata dict with keys: category, name, role

        Returns:
            bool: True if restart successful, False otherwise
        """
        category = meta.get("category", "")
        role = meta.get("role", "worker")
        meta.get("name", "")

        try:
            # Wait before restarting
            if self.process_restart_delay > 0:
                self.logger.debug(
                    "Waiting %ds before restarting %s worker for '%s'",
                    self.process_restart_delay,
                    role,
                    category,
                )
                time.sleep(self.process_restart_delay)

            # Find the corresponding Arr instance
            if not self.arr_manager:
                self.logger.error("ArrManager not available for process restart")
                return False

            arr = self.arr_manager.managed_objects.get(category)
            if not arr:
                self.logger.error("Cannot find Arr instance for category '%s'", category)
                return False

            # Recreate the process based on role
            new_proc = None
            if role == "search" and hasattr(arr, "run_search_loop"):
                new_proc = pathos.helpers.mp.Process(target=arr.run_search_loop, daemon=False)
                if hasattr(arr, "process_search_loop"):
                    arr.process_search_loop = new_proc
            elif role == "torrent" and hasattr(arr, "run_torrent_loop"):
                new_proc = pathos.helpers.mp.Process(target=arr.run_torrent_loop, daemon=False)
                if hasattr(arr, "process_torrent_loop"):
                    arr.process_torrent_loop = new_proc
            else:
                self.logger.error(
                    "Unknown role '%s' for category '%s' or target method not found",
                    role,
                    category,
                )
                return False

            if not new_proc:
                return False

            # Start the new process
            new_proc.start()

            # Update restart tracking
            key = (category, role)
            self._process_restart_counts.setdefault(key, []).append(time.time())

            # Replace in child_processes list
            with contextlib.suppress(ValueError):
                self.child_processes.remove(failed_proc)
            self.child_processes.append(new_proc)

            # Update registry
            self._process_registry.pop(failed_proc, None)
            self._process_registry[new_proc] = meta

            self.logger.notice(
                "Successfully restarted %s worker for category '%s' (restarts in window: %d/%d)",
                role,
                category,
                len(self._process_restart_counts[key]),
                self.max_process_restarts,
            )

            return True

        except Exception as e:
            self.logger.exception(
                "Failed to restart %s worker for category '%s': %s", role, category, e
            )
            return False
