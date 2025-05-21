import logging
from typing import Self
from dataclasses import dataclass
import zlib
import struct

import regex


logger = logging.getLogger(__name__)


@dataclass
class Header:
    rec_version: bytes  # null string
    checker: float  # f32
    version_minor: int  # u16
    version_major: int  # u16
    game_version: float  # f32
    build: int  # u32
    timestamp: int  # s32
    version: tuple[int, int]  # u16[2]
    internal_version: tuple[int, int]  # u16[2]
    # Technically we have the following separation here, but to keep things simple we just treat it as a byte blob
    # It would be useful to fully parse the LobbySettings, but they are quite complex
    #   lobby_settings: LobbySettings
    #   ai_config: AIConfig
    #   replay: Replay
    #   map_info: MapInfo
    #   players: list[Init]
    data: bytes

    @classmethod
    def parse(cls, data: bytes, is_compressed: bool) -> Self:
        """Parse a Header object from given data.

        Args:
            data (bytes): The bytes object containing header data
            is_compressed (bool): Flag if header in given data object is compressed or not

        Returns:
            Self: A parsed Header object
        """
        if is_compressed:
            data = zlib.decompress(data, wbits=-15)

        null_pos = data.find(b"\x00")
        rec_version = data[:null_pos]
        offset = null_pos

        def read(fmt: str):
            nonlocal offset
            size = struct.calcsize(fmt)
            value = struct.unpack_from(fmt, data, offset)
            offset += size

            return value if len(value) > 1 else value[0]

        checker = read("<f")
        version_minor = read("<H")
        version_major = read("<H")
        game_version = read("<f")
        build = read("<I")
        timestamp = read("<i")
        version = read("<HH")
        internal_version = read("<HH")

        return cls(
            rec_version,
            checker,
            version_minor,
            version_major,
            game_version,
            build,
            timestamp,
            version,
            internal_version,
            bytes(data[offset:])
        )

    def pack(self) -> bytes:
        """Pack and compress the current header data into a single bytes object.

        Returns:
            Self: The compressed Header object as bytes
        """
        parts = [
            self.rec_version,
            struct.pack("<f", self.checker),
            struct.pack("<H", self.version_minor),
            struct.pack("<H", self.version_major),
            struct.pack("<f", self.game_version),
            struct.pack("<I", self.build),
            struct.pack("<i", self.timestamp),
            struct.pack("<HH", *self.version),
            struct.pack("<HH", *self.internal_version),
            self.data
        ]

        return zlib.compress(b"".join(parts))[2:-4]

    def get_player_count(self) -> int:
        """Get the player count of the rec file.

        Returns:
            int: The player count
        """
        # To find the player count we use a bit of a shortcut and find the two separators in the lobby settings
        # At that point the structure is like this, so we can extract the player count
        #   u32 Separator;
        #   u32 Separator;
        #   float speed;
        #   u32 treaty_length;
        #   u32 population_limit;
        #   u32 n_players;
        separator_pattern = rb"\xA3\x5F\x02\x00"
        pattern = separator_pattern + separator_pattern
        match = regex.search(pattern, self.data)

        if match is None:
            raise Exception("Failed to get player count")

        _, _, _, player_count = struct.unpack_from("<fIII", self.data, match.end())

        return player_count

    def anonymize_players(self, num_players: int) -> None:
        """Anonymize player data in the rec file. This includes the player names and profile id in the lobby settings and attributes of the file header.

        Args:
            num_players (int): The number of player in the rec file

        Raises:
            Exception: When there was an error anonymizing a player
        """
        anonymized_data = bytearray(self.data)
        offset = 0

        for i in range(1, num_players + 1):
            offset = self._anonymize_next_player(i, offset, anonymized_data)

            if offset == -1:
                raise Exception(f"Could not anonymize player {i}")

        self.data = bytes(anonymized_data)

    @classmethod
    def _anonymize_next_player(cls, id: int, offset: int, data: bytearray) -> int:
        """Anonymize the next player starting from the given offset in the data array.
        Anonymization includes player name and profile in the lobby settings and player name in attributes.

        Args:
            id (int): The player id for the player to be anonymized. Used as replacement name
            offset (int): The offset to start anonymizing the next player
            data (bytearray): The data containing player data. Will be modified

        Returns:
            int: The end position of the anonymized player in the lobby settings or -1 if no player was found
        """
        pattern = rb"\x60\x0A\K(?P<length>[\x01-\xFF])\x00(?P<name>.{0,255}?)\x02\x00\x00\x00(?P<profile_id>.{4})"
        match = regex.search(pattern, data, pos=offset, endpos=int("0x330", 0))

        if match:
            match_start = match.start()
            length, = struct.unpack("<B", match.group("length"))
            original_name_bytes = match.group("name")
            target_name_bytes = f"player {id}".encode()
            target_name_length = len(target_name_bytes)
            logger.info(f"Found player: {str(original_name_bytes, encoding="utf-8")} ({str(target_name_bytes, encoding="utf-8")})")

            # Calculate name start index inside data_bytes
            # pattern is: prefix(2 bytes) + length_byte(1 byte) + \x00 + name(length bytes)
            profile_start_adjusted = match_start + 2 + length + 4 - (length - target_name_length)

            data[match_start:match_start + length + 2] = struct.pack("<H", target_name_length) + target_name_bytes
            data[profile_start_adjusted:profile_start_adjusted + 4] = 4 * b"\x00"

            # Find and anonymize profile in attributes
            length_bytes = struct.pack("<H", (length + 1))
            pattern = regex.escape(length_bytes + original_name_bytes)
            match = regex.search(pattern, data, pos=profile_start_adjusted + 4)

            if match:
                match_start = match.start()
                substitution = struct.pack("<H", len(target_name_bytes) + 1) + target_name_bytes
                data[match_start:match_start + length + 2] = substitution

                # Return match of lobby settings
                return profile_start_adjusted + 4

            logger.warning(f"Did not find attributes string for player: {id}")
            return -1

        logger.warning(f"Did not find player {id} in lobby settings")
        return -1
