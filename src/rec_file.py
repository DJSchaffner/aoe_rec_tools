import struct
from typing import Self
import zlib
from dataclasses import dataclass, fields
import regex


@dataclass
class Meta:
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

        return cls(*struct.unpack("<I?xxxI?xxxIII", data))

    @classmethod
    def byte_length(cls) -> int:
        total = 0
        padding_size = 3

        for field in fields(cls):
            if field.type == int:
                total += 4
            elif field.type == bool:
                total += 1
            else:
                raise TypeError(f"Unsupported type in Meta: {field.type}")

        # Add 3 bytes of padding after each bool
        total += 2 * padding_size

        return total


@dataclass
class RecFile:
    hlen: int
    check: int
    header: bytes
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
            header = file.read(hlen - 8)
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

            file.write(struct.pack("<II", self.hlen, self.check))
            file.write(self.header)
            file.write(struct.pack("<I", self.log_version))
            file.write(self.meta)
            file.write(self.operations)

    def anonymize(self) -> None:
        """Fully anonymize player data in the rec file. This includes the player profiles and names, chat messages and elo."""
        num_players = self._get_player_count()

        try:
            self._anonymize_players(num_players)
            self._anonymize_chat()
            self._anonymize_elo(num_players)
        except Exception as e:
            print(f"Error: {e}")

    def _anonymize_chat(self) -> None:
        """Anonymizes the chat operations in the rec files."""
        anonymized_data = bytearray(self.operations)
        offset = 0

        while True:
            offset = self._anonymize_next_chat_message(offset, anonymized_data)

            if offset < 0:
                break

        self.operations = anonymized_data

    def _anonymize_next_chat_message(self, pos: int, data: bytearray) -> int:
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

        match_start, match_end = match.span()
        length, = struct.unpack("<H", match.group("length"))
        chat_string = data[match_end:match_end + length].decode("utf-8")

        # Extract player id
        match = regex.search(r"\"player\"\:(?P<id>\d)", chat_string)

        if match is None:
            raise Exception(f"Could not extract player id while anonymizing string ({chat_string})")

        # Replace player name in messageAGP part with anonymized name
        player_id = int(match.group("id"))
        changed_chat_string = regex.sub(r"\"messageAGP\":\"@#\d\d(?:\  <platform_icon_.+>  )?\K(?P<name>.+)\: ", f"player {player_id}: ", chat_string)
        changed_length_bytes = struct.pack("<I", len(changed_chat_string))

        data[match_start:match_end + length] = changed_length_bytes + changed_chat_string.encode()

        return match_start + len(changed_chat_string)

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
        pattern = rb"\x06\x00\x00\x00.{1,255}\x02\x00\x00\x00\K[\x00-\x07]\x00\x00\x00"
        offset = 12  # 3 * 4
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

    def _anonymize_players(self, num_players: int) -> None:
        """Anonymize player data in the rec file. This includes the player names and profile id in the lobby settings and attributes of the file header.

        Args:
            num_players (int): The number of player in the rec file

        Raises:
            Exception: When there was an error anonymizing a player
        """
        anonymized_data = bytearray(zlib.decompress(self.header, wbits=-15))
        offset = 0

        for i in range(num_players):
            offset = self._anonymize_next_player(i, offset, anonymized_data)

            if offset == -1:
                raise Exception("Could not anonymize player")

        # Recompress and slice off header + checksum
        self.header = zlib.compress(bytes(anonymized_data))[2:-4]
        self.hlen = len(self.header) + 8

    def _anonymize_next_player(self, id: int, offset: int, data: bytearray) -> int:
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
            target_name_bytes = f"player {id + 1}".encode()
            target_name_length = len(target_name_bytes)
            print(f"Found player with name: {str(original_name_bytes, encoding="utf-8")}")

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
                print(f"Found attributes player string for player: {str(original_name_bytes, encoding="utf-8")}")
                match_start = match.start()
                substitution = struct.pack("<H", len(target_name_bytes) + 1) + target_name_bytes
                data[match_start:match_start + length + 2] = substitution

                # Return match of lobby settings
                return profile_start_adjusted + 4

            print(f"Did not find player attribute string for player {id}")
            return -1

        print(f"Did not find player {id} in lobby settings")
        return -1

    def _get_player_count(self) -> int:
        """Get the player count of the rec file.

        Raises:
            Exception: When the player count could not be retrieved

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
        uncompressed_header = bytearray(zlib.decompress(self.header, wbits=-15))
        separator_pattern = rb"\xA3\x5F\x02\x00"
        pattern = separator_pattern + separator_pattern
        match = regex.search(pattern, uncompressed_header)

        if match is None:
            raise Exception("Failed to get player count")

        _, _, _, player_count = struct.unpack_from("<fIII", uncompressed_header, match.end())

        return player_count
