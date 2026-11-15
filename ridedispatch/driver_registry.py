"""Driver registry: Python dict (open-addressing hash table; Peterson, 1957)."""

from dataclasses import dataclass

from .exceptions import UnknownDriverError, DuplicateDriverError

FREE = "free"
ASSIGNED = "assigned"
OFFLINE = "offline"
_STATUSES = {FREE, ASSIGNED, OFFLINE}


@dataclass
class Driver:
    driver_id: str
    node: object                 # intersection the driver is at
    status: str = FREE
    trips_completed: int = 0


class DriverRegistry:
    def __init__(self):
        self._drivers = {}

    def __len__(self):
        return len(self._drivers)

    def __contains__(self, driver_id):
        return driver_id in self._drivers

    def __iter__(self):
        return iter(self._drivers.values())

    def add(self, driver):
        if driver.driver_id in self._drivers:
            raise DuplicateDriverError(f"driver already registered: {driver.driver_id!r}")
        if driver.status not in _STATUSES:
            raise ValueError(f"bad status {driver.status!r}")
        self._drivers[driver.driver_id] = driver

    def get(self, driver_id):
        try:
            return self._drivers[driver_id]
        except KeyError:
            raise UnknownDriverError(f"unknown driver: {driver_id!r}") from None

    def set_status(self, driver_id, status):
        if status not in _STATUSES:
            raise ValueError(f"bad status {status!r}")
        self.get(driver_id).status = status

    def remove(self, driver_id):
        driver = self.get(driver_id)
        del self._drivers[driver_id]
        return driver

    def count(self, status):
        return sum(1 for d in self._drivers.values() if d.status == status)
