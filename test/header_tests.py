import unittest

from src.header import Header
from sample_data import get_header_compressed, get_header_fabricated, get_header_uncompressed


class HeaderTests(unittest.TestCase):
    def test_parse_with_compressed_data_returns_success(self):
        # Arrange
        data = get_header_compressed()

        # Act
        header = Header.parse(data, is_compressed=True)

        # Assert
        self.assertIsNotNone(header)
        self.assertIsNotNone(header.rec_version)
        self.assertIsNotNone(header.checker)
        self.assertIsNotNone(header.version_minor)
        self.assertIsNotNone(header.version_major)
        self.assertIsNotNone(header.build)
        self.assertIsNotNone(header.timestamp)
        self.assertIsNotNone(header.version)
        self.assertIsNotNone(header.internal_version)
        self.assertIsNotNone(header.data)

    def test_parse_with_uncompressed_data_returns_success(self):
        # Arrange
        data = get_header_uncompressed()

        # Act
        header = Header.parse(data, is_compressed=False)

        # Assert
        self.assertIsNotNone(header)
        self.assertIsNotNone(header.rec_version)
        self.assertIsNotNone(header.checker)
        self.assertIsNotNone(header.version_minor)
        self.assertIsNotNone(header.version_major)
        self.assertIsNotNone(header.build)
        self.assertIsNotNone(header.timestamp)
        self.assertIsNotNone(header.version)
        self.assertIsNotNone(header.internal_version)
        self.assertIsNotNone(header.data)

    def test_parse_should_read_data_properly(self):
        # Arrange
        data = get_header_fabricated()

        # Act
        header = Header.parse(data, is_compressed=False)

        # Assert
        self.assertIsNotNone(header)
        self.assertEqual(header.rec_version, b"\x01\x01\x01\x01\x00")
        self.assertEqual(header.checker, -1)
        self.assertEqual(header.version_minor, 2)
        self.assertEqual(header.version_major, 3)
        self.assertEqual(header.build, 4)
        self.assertEqual(header.timestamp, 5)
        self.assertEqual(header.version, (6, 7))
        self.assertEqual(header.internal_version, (8, 9))
        self.assertEqual(header.data, b"\x0A\x0B\x0C\x0D\x0E\x0F")

    def test_pack_should_return_compressed_data_which_can_be_parsed_again(self):
        # Arrange
        data = get_header_uncompressed()
        header = Header.parse(data, is_compressed=False)

        # Act
        packed = header.pack()

        # Assert
        unpacked = Header.parse(packed, is_compressed=True)
        self.assertIsNotNone(packed)
        self.assertEqual(header, unpacked)
