import os
import unittest
from unittest.mock import patch

from config import get_int


class GetIntTests(unittest.TestCase):
    def test_uses_default_for_invalid_value(self):
        with patch.dict(os.environ, {"TEST_VALUE": "not-a-number"}):
            self.assertEqual(get_int("TEST_VALUE", 7), 7)

    def test_uses_default_below_minimum(self):
        with patch.dict(os.environ, {"TEST_VALUE": "0"}):
            self.assertEqual(get_int("TEST_VALUE", 7, minimum=1), 7)

    def test_returns_valid_value(self):
        with patch.dict(os.environ, {"TEST_VALUE": "12"}):
            self.assertEqual(get_int("TEST_VALUE", 7), 12)


if __name__ == "__main__":
    unittest.main()
