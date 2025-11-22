#!/bin/bash
# qBitrr Docker Restart Wrapper
# This script monitors qBitrr and restarts it on specific exit codes
# Exit code 42 = Intentional restart (update, config reload, etc.)
# Exit code 0 = Normal exit (don't restart)
# Any other code = Error (restart after delay)

set -e

EXIT_CODE_RESTART=42
EXIT_CODE_NORMAL=0
MAX_CONSECUTIVE_FAILURES=5
FAILURE_WINDOW_SECONDS=60

echo "qBitrr Restart Wrapper started at $(date)"
echo "Monitoring for exit code $EXIT_CODE_RESTART to trigger restart"

consecutive_failures=0
last_failure_time=0

while true; do
    echo "Starting qBitrr at $(date)..."

    # Start qBitrr and capture exit code
    python -m qBitrr.main
    EXIT_CODE=$?

    current_time=$(date +%s)

    # Check if this is an intentional restart
    if [ $EXIT_CODE -eq $EXIT_CODE_RESTART ]; then
        echo "Restart requested (exit code $EXIT_CODE_RESTART) at $(date)"
        echo "Restarting qBitrr in 2 seconds..."
        consecutive_failures=0
        sleep 2
        continue
    fi

    # Check if this is a normal exit
    if [ $EXIT_CODE -eq $EXIT_CODE_NORMAL ]; then
        echo "qBitrr exited normally (exit code $EXIT_CODE_NORMAL) at $(date)"
        echo "Stopping container..."
        exit 0
    fi

    # This is an error exit
    echo "ERROR: qBitrr exited with code $EXIT_CODE at $(date)"

    # Track consecutive failures
    time_since_last_failure=$((current_time - last_failure_time))

    if [ $time_since_last_failure -gt $FAILURE_WINDOW_SECONDS ]; then
        # Reset counter if enough time has passed
        consecutive_failures=1
    else
        consecutive_failures=$((consecutive_failures + 1))
    fi

    last_failure_time=$current_time

    # Check if we've hit the failure limit
    if [ $consecutive_failures -ge $MAX_CONSECUTIVE_FAILURES ]; then
        echo "ERROR: qBitrr has failed $consecutive_failures times in $FAILURE_WINDOW_SECONDS seconds"
        echo "Maximum consecutive failures reached. Stopping container."
        echo "Please check logs and configuration before restarting."
        exit 1
    fi

    # Calculate backoff delay
    backoff_delay=$((consecutive_failures * 5))
    echo "Restart attempt $consecutive_failures/$MAX_CONSECUTIVE_FAILURES"
    echo "Waiting $backoff_delay seconds before restart..."
    sleep $backoff_delay
done
