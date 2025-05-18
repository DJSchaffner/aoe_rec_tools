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
        self._anonymize_players()
        self._anonymize_chat()
        self._anonymize_elo()

    def _anonymize_chat(self) -> None:
        pass

    def _anonymize_elo(self) -> None:
        # Anonymize Elo (Stored after operations it seems )
        """
        00 00 05 00 00 00 0B 02 01 00 00 49 6B 28 00 06 <- 06 Should be the start of post game operation block
        00 00 00 49 6B 28 00 04 00 00 00 01 00 00 00 01
        00 00 00 03 00 00 00 01 01 02 00 00 00 00 00 00
        00 1F 0A 00 00 4A 06 00 00 01 00 00 00 9E 09 00 <- 4A06 is the elo of me (p2)
        00 54 06 00 00 26 00 00 00 02 00 00 00 02 00 00 <- 5406 is the elo of opponent (p5)
        00 01 00 00 00 CE A4 59 B1 05 DB 7B 43
        """
        return

    def _anonymize_players(self) -> None:
        # Decompress header
        anonymized_data = bytearray(zlib.decompress(self.header, wbits=-15))
        count = 0
        offset = 0

        while (offset := self._anonymize_next_player(count, offset, anonymized_data)) >= 0:
            count += 1

            if (count >= 8):
                print("Error: Tried to anonymize too many players")
                break

        # Recompress and slice off header + checksum
        self.header = zlib.compress(bytes(anonymized_data), level=6)[2:-4]
        self.hlen = len(self.header) + 8

    def _anonymize_next_player(self, id: int, offset: int, data: bytearray) -> int:
        pattern = rb"\x60\x0A(?!\x00)\K(?P<length>.)\x00(?P<name>.{0,255}?)\x02\x00\x00\x00(?P<profile_id>.{4})"
        match = regex.search(pattern, data, pos=offset, endpos=int("0x330", 0))
        target_name_bytes = f"player {id + 1}".encode()
        target_name_length = len(target_name_bytes)

        if match:
            match_start, _ = match.span()
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
                match_start, _ = match.span()
                substitution = (len(target_name_bytes) + 1).to_bytes(2, byteorder="little") + target_name_bytes
                data[match_start:match_start + length + 2] = substitution

            # Return match of lobby settings
            return profile_start_adjusted + 4

        return -1
