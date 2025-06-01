import logging
import struct
from typing import Self
from dataclasses import dataclass, fields
import regex

from aoe_rec_tools.errors import AnonymizationError
from aoe_rec_tools.header import Header
from aoe_rec_tools.operations import Operation, PostgameOperation


logger = logging.getLogger(__name__)


@dataclass
class Meta:
    PACK_FORMAT = "<I?xxxI?xxxIII"

    checksum_interval: int
    multiplayer: bool
    rec_owner: int
    reveal_map: bool
    use_sequence_numbers: int
    number_of_chapters: int
    aok_or_de: int

    def pack(self) -> bytes:
        return struct.pack(self.PACK_FORMAT, *[getattr(self, field.name) for field in fields(self)])

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        if len(data) < struct.calcsize(cls.PACK_FORMAT):
            raise ValueError("Meta block too short (must be at least 28 bytes)")

        return cls(*struct.unpack(cls.PACK_FORMAT, data[:struct.calcsize(cls.PACK_FORMAT)]))

    @classmethod
    def byte_length(cls) -> int:
        return struct.calcsize(cls.PACK_FORMAT)


@dataclass
class RecFile:
    CHAT_OPERATION_PATTERN = regex.compile(rb"\x04\x00\x00\x00\xFF\xFF\xFF\xFF\K(?P<length>.{2})\x00\x00")
    SYSTEM_CHAT_PATTERN = regex.compile(rb"<player_id,(?P<player_id>.),0>")
    CHAT_MESSAGE_PATTERN = regex.compile(rb"\"messageAGP\":\"@#\d\d(?:\  <platform_icon_.+>  )?\K(?P<name>.+)\: ")

    header_length: int
    check: int
    header: Header
    log_version: int
    meta: Meta
    operations: list[Operation]

    @classmethod
    def parse(cls, file_name: str) -> Self:
        """Parse a RecFile object from a given file name.

        Args:
            file_name (str): The file name and path if necessary

        Returns:
            Self: A parsed RecFile object
        """
        with open(file_name, "rb") as file:
            # Read sections using little endian
            header_length, check = struct.unpack("<II", file.read(8))
            header = Header.parse(file.read(header_length - 8), True)
            log_version, = struct.unpack("<I", file.read(4))
            meta = Meta.from_bytes(file.read(Meta.byte_length()))
            operations = Operation.parse_operations(file.read())

        return RecFile(header_length, check, header, log_version, meta, operations)

    def write(self, file_name: str) -> None:
        """Write the content of a RecFile object back to a aoe2 rec file with the given name.

        Args:
            file_name (str): The output name of the file
        """
        with open(file_name, "wb") as file:
            compressed_header = self.header.pack()
            self.header_length = len(compressed_header) + 8

            file.write(struct.pack("<II", self.header_length, self.check))
            file.write(compressed_header)
            file.write(struct.pack("<I", self.log_version))
            file.write(self.meta.pack())

            for operation in self.operations:
                file.write(operation.pack())

    def anonymize(self, remove_system_chat: bool, remove_player_chat: bool) -> None:
        """Fully anonymize player data in the rec file. This includes the player profiles and names, chat messages and elo.

        Raises:
            Exception: When anonymization failed
        """
        num_players = self.header.get_player_count()

        self._anonymize_players(num_players)
        self._anonymize_chat(remove_system_chat, remove_player_chat)
        self._anonymize_elo()

    def _anonymize_players(self, num_players: int) -> None:
        """Anonymizes the player names in the rec file."""
        self.header.anonymize_players(num_players)

    def _anonymize_chat(self, remove_system_chat: bool, remove_player_chat: bool) -> None:
        """Anonymizes the chat operations in the rec file."""
        pass

    @classmethod
    def _anonymize_next_chat_message(cls, pos: int, data: bytearray, remove_system_chat: bool, remove_player_chat: bool) -> int:
        """Anonymize the next chat message starting from the given position. Anonymization only affects the messages shown in the separate chat window.

        Args:
            pos (int): The Starting position to find the next chat operation
            data (bytearray): The data containing the chat operations
            remove_system_chat (bool): Remove system chat when true. Otherwise keep it
            remove_player_chat (bool): Remove player chat when true. Otherwise keep it

        Raises:
            Exception: When the player id could not be extracted from the chat message

        Returns:
            int: The End position of the anonymized chat message or -1 if none was found
        """
        # Find next chat operation
        operation_match = regex.search(cls.CHAT_OPERATION_PATTERN, data, pos=pos)

        # Did not find a chat operation
        if operation_match is None:
            return -1

        operation_start = operation_match.start() - 8
        operation_end = operation_match.end() + struct.unpack("<H", operation_match.group("length"))[0]
        operation_data = bytes(data[operation_start:operation_end])
        operation_match_start = operation_match.start()
        payload_bytes = bytearray(operation_data[12:])
        player_id = payload_bytes[10] - ord('0')

        def drop_operation():
            del data[operation_start:operation_end]
            return operation_start

        def set_length(length: int):
            data[operation_match_start:operation_match_start + 4] = struct.pack("<I", length)

        def set_payload(payload: bytes):
            data[operation_match_start + 4:operation_end] = payload

        # Shortcut for dropping all chat operations
        if remove_player_chat and remove_system_chat:
            return drop_operation()

        # Try to find player substitution string in chat message
        system_match = regex.search(cls.SYSTEM_CHAT_PATTERN, payload_bytes)
        is_player_message = False

        if system_match is None:
            is_player_message = True

        if ((not is_player_message and remove_system_chat) or (is_player_message and remove_player_chat)):
            return drop_operation()

        # Anonymize player message
        if is_player_message and not remove_player_chat:
            # Replace player name in messageAGP part with anonymized name
            changed_payload_bytes = regex.sub(cls.CHAT_MESSAGE_PATTERN, f"player {player_id}: ".encode(), payload_bytes)
            set_length(len(changed_payload_bytes))
            set_payload(changed_payload_bytes)

        # Fix system message
        # It gets the job done, but looks different from a normal message and normally this shouldn't be a problem
        """
        if not is_player_message and not remove_system_chat:
            system_match_start, system_match_end = system_match.span()
            replacement = f"player {player_id}".encode()
            new_payload_bytes = payload_bytes[:system_match_start] + replacement + payload_bytes[system_match_end + 1:]

            # Update length and message
            set_length(len(new_payload_bytes))
            set_payload(new_payload_bytes)
        """

        return operation_start + 1

    def _anonymize_elo(self) -> None:
        """Anonymize players elo in the rec file. Capture Age displays this data.

        Args:
            num_players (int): The number of players in the rec file

        Raises:
            Exception: When the elo block could not be found
        """
        postgame_operation: PostgameOperation = self.operations[-1]
        leaderboard_block = [x for x in postgame_operation.blocks if isinstance(x, PostgameOperation.LeaderboardsBlock)][0]

        if leaderboard_block is None:
            raise AnonymizationError("Could not anonymize elo")

        for leaderboard in leaderboard_block.leaderboards:
            for player in leaderboard.players:
                fake_rating = 3000
                logger.info(f"Rating for player {player.player_id + 1}({player.rating}) set to: {fake_rating}")
                player.rank = 1
                player.rating = fake_rating
