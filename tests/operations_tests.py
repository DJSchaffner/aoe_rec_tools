import unittest

from aoe_rec_tools.operations import PostgameOperation
from sample_data import get_postgame_fabricated


class OperationsTests(unittest.TestCase):
    def test_postgame_parse_returns_success(self):
        # Arrange
        data = get_postgame_fabricated()

        # Act
        postgame_operation = PostgameOperation.parse(data, 0)

        # Assert
        self.assertIsNotNone(postgame_operation.data)
        self.assertIsNotNone(postgame_operation.unknown)
        self.assertIsNotNone(postgame_operation.version)
        self.assertIsNotNone(postgame_operation.blocks)

    def test_postgame_parse_should_read_fabricated_data_properly(self):
        # Arrange
        data = get_postgame_fabricated()

        # Act
        postgame_operation = PostgameOperation.parse(data, 0)

        # Assert
        self.assertEqual(postgame_operation.data, data)
        self.assertEqual(postgame_operation.unknown, data[-8:][::-1])
        self.assertEqual(postgame_operation.version, 1)
        self.assertEqual(len(postgame_operation.blocks), 2)
        self.assertTrue(isinstance(postgame_operation.blocks[0], PostgameOperation.LeaderboardsBlock))
        self.assertTrue(isinstance(postgame_operation.blocks[1], PostgameOperation.WorldTimeBlock))

    def test_postgame_pack_should_produce_original_data(self):
        # Arrange
        data = get_postgame_fabricated()

        # Act
        postgame_operation = PostgameOperation.parse(data, 0)
        packed = postgame_operation.pack()

        # Assert
        self.assertEqual(data.hex(" ").upper(), packed.hex(" ").upper())
