from typing import Self
import zlib
from numpy import uint32
from dataclasses import dataclass, fields


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

    def anonymize_players(self) -> None:
        # Decompress header
        uncompressed_data = zlib.decompress(self.header, wbits=-15)

        # Recompress and slice off header + checksum
        self.header = zlib.compress(bytes(uncompressed_data), level=6)[2:-4]
        self.hlen = len(self.header) + 8
