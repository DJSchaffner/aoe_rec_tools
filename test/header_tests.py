import unittest

from src.header import Header
from sample_data import get_header_compressed


class HeaderTests(unittest.TestCase):
    def test_parse_with_compressed_data_returns_success(self):
        # Arrange
        data = get_header_compressed()

        # Act
        header = Header.parse(data, is_compressed=True)

        # Assert
        self.assertIsNotNone(header)

    def test_parse_with_uncompressed_data_returns_success(self):
        # Arrange
        data = get_header_compressed()

        # Act
        header = Header.parse(data, is_compressed=True)

        # Assert
        self.assertIsNotNone(header)
