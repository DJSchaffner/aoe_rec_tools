import struct
from typing import Self
from dataclasses import dataclass
import regex

from header import Header


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

    def anonymize(self, keep_chat: bool) -> None:
        """Fully anonymize player data in the rec file. This includes the player profiles and names, chat messages and elo.

        Raises:
            Exception: When anonymization failed
        """
        num_players = self.header.get_player_count()

        self._anonymize_players(num_players)
        self._anonymize_chat(keep_chat)
        self._anonymize_elo(num_players)

    def _anonymize_players(self, num_players: int) -> None:
        """Anonymizes the player names in the rec file."""
        self.header.anonymize_players(num_players)

    def _anonymize_chat(self, keep_chat: bool) -> None:
        """Anonymizes the chat operations in the rec file."""
        anonymized_data = bytearray(self.operations)
        offset = 0

        while True:
            offset = self._anonymize_next_chat_message(offset, anonymized_data, keep_chat)

            if offset < 0:
                break

        self.operations = anonymized_data

    @classmethod
    def _anonymize_next_chat_message(cls, pos: int, data: bytearray, keep_chat: bool) -> int:
        """Anonymize the next chat message starting from the given position. Anonymization only affects the messages shown in the separate chat window.

        Args:
            pos (int): The Starting position to find the next chat operation
            data (bytearray): The data containing the chat operations

        Raises:
            Exception: When the player id could not be extracted from the chat message

        Returns:
            int: The End position of the anonymized chat message or -1 if none was found
        """
        # Find next chat operation
        pattern = rb"\x04\x00\x00\x00\xFF\xFF\xFF\xFF\K(?P<length>.{2})\x00\x00"
        match = regex.search(pattern, data, pos=pos)

        if match is None:
            return -1

        if not keep_chat:
            operation_start = match.start() - 8
            operation_end = match.end() + struct.unpack("<H", match.group("length"))[0]

            del data[operation_start:operation_end]

            return operation_start

        match_start, match_end = match.span()
        length, = struct.unpack("<H", match.group("length"))
        # This can fail because encoding is not fixed it seems
        chat_string = data[match_end:match_end + length].decode("utf-8")

        # Extract player id
        match = regex.search(r"\"player\"\:(?P<id>\d)", chat_string)

        if match is None:
            raise Exception(f"Could not extract player id while anonymizing string ({chat_string})")

        # Replace player name in messageAGP part with anonymized name
        player_id = int(match.group("id"))
        changed_chat_bytes = regex.sub(r"\"messageAGP\":\"@#\d\d(?:\  <platform_icon_.+>  )?\K(?P<name>.+)\: ", f"player {player_id}: ", chat_string).encode()
        changed_length_bytes = struct.pack("<I", len(changed_chat_bytes))

        data[match_start:match_end + length] = changed_length_bytes + changed_chat_bytes

        return match_start + len(changed_chat_bytes)

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
            print(f"Rating for player {player_id + 1}({rating}) set to: {fake_rating}")

        self.operations = anonymized_data
