"""Radarr minimum-availability helpers (split from Arr.minimum_availability_check)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from qBitrr.arss._shared import JsonObject

if TYPE_CHECKING:
    from qBitrr.arss.base import ArrBase as Arr


def minimum_availability_check(arr: Arr, db_entry: JsonObject) -> bool:
    """Return whether a Radarr movie entry meets its configured minimum availability."""
    inCinemas = (
        datetime.strptime(db_entry["inCinemas"], "%Y-%m-%dT%H:%M:%SZ")
        if "inCinemas" in db_entry
        else None
    )
    digitalRelease = (
        datetime.strptime(db_entry["digitalRelease"], "%Y-%m-%dT%H:%M:%SZ")
        if "digitalRelease" in db_entry
        else None
    )
    physicalRelease = (
        datetime.strptime(db_entry["physicalRelease"], "%Y-%m-%dT%H:%M:%SZ")
        if "physicalRelease" in db_entry
        else None
    )
    now = datetime.now()
    if db_entry["year"] > now.year or db_entry["year"] == 0:
        arr.logger.trace(
            "Skipping 1 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
            db_entry["title"],
            db_entry["minimumAvailability"],
            inCinemas,
            digitalRelease,
            physicalRelease,
        )
        return False
    elif db_entry["year"] < now.year - 1 and db_entry["year"] != 0:
        arr.logger.trace(
            "Grabbing 2 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
            db_entry["title"],
            db_entry["minimumAvailability"],
            inCinemas,
            digitalRelease,
            physicalRelease,
        )
        return True
    elif (
        "inCinemas" not in db_entry
        and "digitalRelease" not in db_entry
        and "physicalRelease" not in db_entry
        and db_entry["minimumAvailability"] == "released"
    ):
        arr.logger.trace(
            "Grabbing 3 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
            db_entry["title"],
            db_entry["minimumAvailability"],
            inCinemas,
            digitalRelease,
            physicalRelease,
        )
        return True
    elif (
        "digitalRelease" in db_entry
        and "physicalRelease" in db_entry
        and db_entry["minimumAvailability"] == "released"
    ):
        if digitalRelease <= now or physicalRelease <= now:
            arr.logger.trace(
                "Grabbing 4 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return True
        else:
            arr.logger.trace(
                "Skipping 5 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return False
    elif ("digitalRelease" in db_entry or "physicalRelease" in db_entry) and db_entry[
        "minimumAvailability"
    ] == "released":
        if "digitalRelease" in db_entry:
            if digitalRelease <= now:
                arr.logger.trace(
                    "Grabbing 6 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return True
            else:
                arr.logger.trace(
                    "Skipping 7 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return False
        elif "physicalRelease" in db_entry:
            if physicalRelease <= now:
                arr.logger.trace(
                    "Grabbing 8 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return True
            else:
                arr.logger.trace(
                    "Skipping 9 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return False
    elif (
        "inCinemas" not in db_entry
        and "digitalRelease" not in db_entry
        and "physicalRelease" not in db_entry
        and db_entry["minimumAvailability"] == "inCinemas"
    ):
        arr.logger.trace(
            "Grabbing 10 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
            db_entry["title"],
            db_entry["minimumAvailability"],
            inCinemas,
            digitalRelease,
            physicalRelease,
        )
        return True
    elif "inCinemas" in db_entry and db_entry["minimumAvailability"] == "inCinemas":
        if inCinemas <= now:
            arr.logger.trace(
                "Grabbing 11 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return True
        else:
            arr.logger.trace(
                "Skipping 12 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return False
    elif "inCinemas" not in db_entry and db_entry["minimumAvailability"] == "inCinemas":
        if "digitalRelease" in db_entry:
            if digitalRelease <= now:
                arr.logger.trace(
                    "Grabbing 13 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return True
            else:
                arr.logger.trace(
                    "Skipping 14 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return False
        elif "physicalRelease" in db_entry:
            if physicalRelease <= now:
                arr.logger.trace(
                    "Grabbing 15 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return True
            else:
                arr.logger.trace(
                    "Skipping 16 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return False
        else:
            arr.logger.trace(
                "Skipping 17 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return False
    elif db_entry["minimumAvailability"] == "announced":
        arr.logger.trace(
            "Grabbing 18 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
            db_entry["title"],
            db_entry["minimumAvailability"],
            inCinemas,
            digitalRelease,
            physicalRelease,
        )
        return True
    else:
        arr.logger.trace(
            "Skipping 19 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
            db_entry["title"],
            db_entry["minimumAvailability"],
            inCinemas,
            digitalRelease,
            physicalRelease,
        )
        return False
