import struct
from typing import Self
import zlib
from numpy import uint32
from dataclasses import dataclass, fields
import regex


@dataclass
class Meta:
    checksum_interval: uint32
    multiplayer: bool
    rec_owner: uint32
    reveal_map: bool
    use_sequence_numbers: uint32
    number_of_chapters: uint32
    aok_or_de: uint32

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        if len(data) < 28:
            raise ValueError("Meta block too short (must be at least 28 bytes)")

        return cls(
            checksum_interval=uint32(int.from_bytes(data[0:4], "little")),
            multiplayer=bool(data[4]),
            rec_owner=uint32(int.from_bytes(data[8:12], "little")),
            reveal_map=bool(data[12]),
            use_sequence_numbers=uint32(int.from_bytes(data[16:20], "little")),
            number_of_chapters=uint32(int.from_bytes(data[20:24], "little")),
            aok_or_de=uint32(int.from_bytes(data[24:28], "little")),
        )

    @classmethod
    def byte_length(cls) -> int:
        total = 0
        padding_size = 3

        for field in fields(cls):
            if field.type == uint32:
                total += 4
            elif field.type == bool:
                total += 1
            else:
                raise TypeError(f"Unsupported type in Meta: {field.type}")
        # Add 3 bytes of padding after each bool
        total += 2 * padding_size  # for the two 3-byte paddings

        return total


@dataclass
class RecFile:
    hlen: uint32
    check: uint32
    header: bytes
    log_version: uint32
    meta: bytes
    operations: bytes

    def parse(file_name: str) -> Self:
        with open(file_name, "rb") as file:
            # Read sections using little endian
            hlen = uint32(int.from_bytes(file.read(4), "little"))
            check = uint32(int.from_bytes(file.read(4), "little"))
            header = file.read(hlen - 8)
            log_version = uint32(int.from_bytes(file.read(4), "little"))

            meta_len = Meta.byte_length()
            meta = file.read(meta_len)
            operations = file.read()

        return RecFile(hlen, check, header, log_version, meta, operations)

    def write(self, file_name: str) -> None:
        with open(file_name, "wb") as file:
            file.write(int(self.hlen).to_bytes(4, "little"))
            file.write(int(self.check).to_bytes(4, "little"))
            file.write(self.header)
            file.write(int(self.log_version).to_bytes(4, "little"))
            file.write(self.meta)
            file.write(self.operations)

    def anonymize(self) -> None:
        num_players = self._get_player_count()

        try:
            self._anonymize_players(num_players)
            self._anonymize_chat()
            self._anonymize_elo(num_players)
        except Exception as e:
            print(f"Error: {e}")

    def _anonymize_chat(self) -> None:
        anonymized_data = bytearray(self.operations)
        offset = 0

        while True:
            offset = self._anonymize_next_chat_message(offset, anonymized_data)
            if offset < 0:
                break

        self.operations = anonymized_data

    def _anonymize_next_chat_message(self, pos: int, data: bytearray) -> int:
        pattern = rb"\x04\x00\x00\x00\xFF\xFF\xFF\xFF\K(?P<length>.)\x00\x00\x00"
        match = regex.search(pattern, data, pos=pos)

        if match is None:
            return -1

        match_start, match_end = match.span()
        length = int.from_bytes(match.group("length"), byteorder="little")
        chat_string = data[match_end:match_end + length].decode("ascii")

        # Extract player id
        match = regex.search(r"\"player\"\:(?P<id>\d)", chat_string)

        if match is None:
            raise Exception(f"Could not extract player id while anonymizing string ({chat_string})")

        player_id = int(match.group("id"))

        # Replace player name in messageAGP part with anonymized name
        chat_string = regex.sub(r"\"messageAGP\":\"@#\d\d(?:\  <platform_icon_.+>  )?\K(?P<name>\w+)\:", f"player {player_id}:", chat_string)
        changed_length_bytes = len(chat_string).to_bytes(4, "little")

        data[match_start:match_end + length] = changed_length_bytes + chat_string.encode()

        return match_start + len(chat_string)

    def _anonymize_elo(self, num_players: int) -> None:
        # Wild guess for now
        MAX_POSTGAME_SIZE = 255
        anonymized_data = bytearray(self.operations)
        pattern = rb"\x06\x00\x00\x00.{1,255}\x02\x00\x00\x00\K\x00\x00\x00\x00"
        pos = len(self.operations) - MAX_POSTGAME_SIZE
        match = regex.search(pattern, anonymized_data, pos=pos)

        if match is None:
            raise Exception("Could not anonymize elo")

        # From this point we seem to have a structure that follows this pattern for each player
        # u32 player_id
        # u32 unknown
        # u32 rating
        base_pos = match.start()
        offset = 3 * 4
        for i in range(num_players):
            block_pos = i * offset + base_pos
            player_id, unknown, rating = struct.unpack_from("<III", anonymized_data, block_pos)

            fake_rating = 3000
            anonymized_data[block_pos:block_pos + offset] = struct.pack("<III", player_id, unknown, fake_rating)

            print(f"Rating for player {player_id + 1}({rating}) set to: {fake_rating}")

        self.operations = anonymized_data

    def _anonymize_players(self, num_players: int) -> None:
        anonymized_data = bytearray(zlib.decompress(self.header, wbits=-15))
        offset = 0

        for i in range(num_players):
            offset = self._anonymize_next_player(i, offset, anonymized_data)
            if offset == -1:
                raise Exception("Could not anonymize player")

        # Recompress and slice off header + checksum
        self.header = zlib.compress(bytes(anonymized_data), level=6)[2:-4]
        self.hlen = len(self.header) + 8

    def _anonymize_next_player(self, id: int, offset: int, data: bytearray) -> int:
        pattern = rb"\x60\x0A(?!\x00)\K(?P<length>.)\x00(?P<name>.{0,255}?)\x02\x00\x00\x00(?P<profile_id>.{4})"
        match = regex.search(pattern, data, pos=offset, endpos=int("0x330", 0))
        target_name_bytes = f"player {id + 1}".encode()
        target_name_length = len(target_name_bytes)

        if match:
            match_start = match.start()
            length_byte = match.group("length")
            length = int.from_bytes(length_byte, byteorder="little")
            original_name_bytes = match.group("name")
            print(f"Found player with name: {str(original_name_bytes, encoding="ascii")}")

            # Calculate name start index inside data_bytes
            # pattern is: prefix(2 bytes) + length_byte(1 byte) + \x00 + name(length bytes)
            profile_start_adjusted = match_start + 2 + length + 4 - (length - target_name_length)

            data[match_start:match_start + length + 2] = target_name_length.to_bytes(2, byteorder="little") + target_name_bytes
            data[profile_start_adjusted:profile_start_adjusted + 4] = 4 * b"\x00"

            # Find and anonymize profile in attributes
            length_bytes = (length + 1).to_bytes(2, byteorder="little")
            pattern = length_bytes + original_name_bytes
            match = regex.search(pattern, data, pos=profile_start_adjusted + 4)

            if match:
                print(f"Found attributes player string for player: {str(original_name_bytes, encoding="ascii")}")
                match_start = match.start()
                substitution = (len(target_name_bytes) + 1).to_bytes(2, byteorder="little") + target_name_bytes
                data[match_start:match_start + length + 2] = substitution

            # Return match of lobby settings
            return profile_start_adjusted + 4

        return -1

    def _get_player_count(self) -> int:
        # To find the player count we use a bit of a shortcut and find the two separators in the lobby settings
        # At that point the structure is like this, so we can extract the player count
        #   u32 Separator;
        #   u32 Separator;
        #   float speed;
        #   u32 treaty_length;
        #   u32 population_limit;
        #   u32 n_players;
        uncompressed_header = bytearray(zlib.decompress(self.header, wbits=-15))
        separator_pattern = b"\xA3\x5F\x02\x00"
        pattern = separator_pattern + separator_pattern
        match = regex.search(pattern, uncompressed_header)

        if match is None:
            raise Exception("Failed to get player count")

        match_end = match.end()
        offset = 4 * 3
        position = match_end + offset
        return int.from_bytes(uncompressed_header[position:position + 4], byteorder="little")
