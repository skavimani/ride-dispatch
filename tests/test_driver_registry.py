import unittest

from ridedispatch import (Driver, DriverRegistry, FREE, ASSIGNED,
                          UnknownDriverError, DuplicateDriverError)


class TestDriverRegistry(unittest.TestCase):
    def test_add_get_status_remove(self):
        reg = DriverRegistry()
        reg.add(Driver("d1", "A"))
        reg.add(Driver("d2", "B"))
        reg.set_status("d1", ASSIGNED)
        self.assertEqual(reg.get("d1").status, ASSIGNED)
        self.assertEqual(reg.count(FREE), 1)
        reg.remove("d2")
        self.assertNotIn("d2", reg)
        self.assertEqual(len(reg), 1)

    def test_errors(self):
        reg = DriverRegistry()
        reg.add(Driver("d1", "A"))
        with self.assertRaises(DuplicateDriverError):
            reg.add(Driver("d1", "B"))
        with self.assertRaises(UnknownDriverError):
            reg.get("ghost")
        with self.assertRaises(ValueError):
            reg.set_status("d1", "sleeping")


if __name__ == "__main__":
    unittest.main()
