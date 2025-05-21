import logging
import struct
from typing import Self
from dataclasses import dataclass
import regex

from header import Header


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

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        if len(data) < 28:
            raise ValueError("Meta block too short (must be at least 28 bytes)")

        return cls(*struct.unpack(cls.PACK_FORMAT, data))

    @classmethod
    def byte_length(cls) -> int:
        return struct.calcsize(cls.PACK_FORMAT)


@dataclass
class RecFile:
    hlen: int
    check: int
    header: Header
    log_version: int
    meta: bytes
    operations: bytes

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
            hlen, check = struct.unpack("<II", file.read(8))
            header = Header.parse(file.read(hlen - 8), True)
            log_version, = struct.unpack("<I", file.read(4))
            meta = file.read(Meta.byte_length())
            operations = file.read()

        return RecFile(hlen, check, header, log_version, meta, operations)

    def write(self, file_name: str) -> None:
        """Write the content of a RecFile object back to a aoe2 rec file with the given name.

        Args:
            file_name (str): The output name of the file
        """
        with open(file_name, "wb") as file:
            compressed_header = self.header.pack()
            self.hlen = len(compressed_header) + 8

            file.write(struct.pack("<II", self.hlen, self.check))
            file.write(compressed_header)
            file.write(struct.pack("<I", self.log_version))
            file.write(self.meta)
            file.write(self.operations)

    def anonymize(self, keep_system_chat: bool, keep_player_chat: bool) -> None:
        """Fully anonymize player data in the rec file. This includes the player profiles and names, chat messages and elo.

        Raises:
            Exception: When anonymization failed
        """
        num_players = self.header.get_player_count()

        self._anonymize_players(num_players)
        self._anonymize_chat(keep_system_chat, keep_player_chat)
        self._anonymize_elo(num_players)

    def _anonymize_players(self, num_players: int) -> None:
        """Anonymizes the player names in the rec file."""
        self.header.anonymize_players(num_players)

    def _anonymize_chat(self, keep_system_chat: bool, keep_player_chat: bool) -> None:
        """Anonymizes the chat operations in the rec file."""
        anonymized_data = bytearray(self.operations)
        offset = 0

        while True:
            offset = self._anonymize_next_chat_message(offset, anonymized_data, keep_system_chat, keep_player_chat)

            if offset < 0:
                break

        self.operations = anonymized_data

    @classmethod
    def _anonymize_next_chat_message(cls, pos: int, data: bytearray, keep_system_chat: bool, keep_player_chat: bool) -> int:
        """Anonymize the next chat message starting from the given position. Anonymization only affects the messages shown in the separate chat window.

        Args:
            pos (int): The Starting position to find the next chat operation
            data (bytearray): The data containing the chat operations
            keep_system_chat (bool): Keep system chat when true. Will also try to fix system chat messages. Otherwise drop it
            keep_player_chat (bool): Keep player chat when true. Otherwise drop it. Can cause issues with decoding

        Raises:
            Exception: When the player id could not be extracted from the chat message

        Returns:
            int: The End position of the anonymized chat message or -1 if none was found
        """
        # Find next chat operation
        pattern = rb"\x04\x00\x00\x00\xFF\xFF\xFF\xFF\K(?P<length>.{2})\x00\x00"
        operation_match = regex.search(pattern, data, pos=pos)

        # Did not find a chat operation
        if operation_match is None:
            return -1

        operation_start = operation_match.start() - 8
        operation_end = operation_match.end() + struct.unpack("<H", operation_match.group("length"))[0]
        operation_data = bytes(data[operation_start:operation_end])
        operation_match_start = operation_match.start()
        payload_bytes = bytearray(operation_data[12:])

        def drop_operation():
            del data[operation_start:operation_end]
            return operation_start

        def set_length(length: int):
            data[operation_match_start:operation_match_start + 4] = struct.pack("<I", length)

        def set_payload(payload: bytes):
            data[operation_match_start + 4:operation_end] = payload

        # Drop all chat operations
        if not keep_player_chat and not keep_system_chat:
            return drop_operation()

        # Extract player id
        # Find -> "player":?,
        pattern = rb"\x22\x70\x6C\x61\x79\x65\x72\x22\x3A(?P<id>.)\x2C"
        player_id_match = regex.search(pattern, payload_bytes)

        if player_id_match is None:
            raise Exception(f"Could not extract player id while anonymizing string ({payload_bytes})")

        # Replace player name in messageAGP part with anonymized name
        player_id = int(player_id_match.group("id"))

        # Find -> <player_id,?,0>
        # We don't want to decode the json to avoid errors with encoding
        pattern = rb"\x3C\x70\x6C\x61\x79\x65\x72\x5F\x69\x64\x2C(?P<player_id>.)\x2C\x30"
        system_match = regex.search(pattern, payload_bytes)
        is_player_message = False

        if system_match is None:
            is_player_message = True

        if ((not is_player_message and not keep_system_chat) or (is_player_message and not keep_player_chat)):
            return drop_operation()

        # Anonymize player message
        if is_player_message and keep_player_chat:
            try:
                # This can fail because encoding is not fixed it seems
                json_string = payload_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raise Exception("Could not anonymize player chat because decoding failed")

            changed_json_bytes = regex.sub(r"\"messageAGP\":\"@#\d\d(?:\  <platform_icon_.+>  )?\K(?P<name>.+)\: ", f"player {player_id}: ", json_string).encode()
            set_length(len(changed_json_bytes))
            set_payload(changed_json_bytes)

        # Fix system message
        if not is_player_message and keep_system_chat:
            system_match_start, system_match_end = system_match.span()
            replacement = f"player {player_id}".encode()
            new_payload_bytes = payload_bytes[:system_match_start] + replacement + payload_bytes[system_match_end + 1:]

            # Update length and message
            set_length(len(new_payload_bytes))
            set_payload(new_payload_bytes)

        return operation_start + 1

    def _anonymize_elo(self, num_players: int) -> None:
        """Anonymize players elo in the rec file. Capture Age displays this data.

        Args:
            num_players (int): The number of players in the rec file

        Raises:
            Exception: When the elo block could not be found
        """
        # Wild guess for now
        MAX_POSTGAME_SIZE = 255
        anonymized_data = bytearray(self.operations)
        # Operation 6 = Postgame. Pattern:
        # WorldTime(u32, u32),
        # Leaderboards(u32, u32, {
        #    u32, u16, u32(num_players), {Players}
        # }
        pattern = rb"\x06\x00\x00\x00.{22,255}" + struct.pack("<I", num_players) + rb"\K[\x00-\x07]\x00\x00\x00"
        offset = struct.calcsize("<III")
        pos = len(self.operations) - MAX_POSTGAME_SIZE
        endpos = len(self.operations) - 8 - (num_players * offset)
        match = regex.search(pattern, anonymized_data, pos=pos, endpos=endpos)

        if match is None:
            raise Exception("Could not anonymize elo")

        # From this point we seem to have a structure that follows this pattern for each player
        # u32 player_id
        # u32 unknown
        # u32 rating
        base_pos = match.start()
        for i in range(num_players):
            block_pos = i * offset + base_pos
            player_id, unknown, rating = struct.unpack_from("<III", anonymized_data, block_pos)

            fake_rating = 3000
            struct.pack_into("<III", anonymized_data, block_pos, player_id, unknown, fake_rating)
            logger.info(f"Rating for player {player_id + 1}({rating}) set to: {fake_rating}")

        self.operations = anonymized_data
