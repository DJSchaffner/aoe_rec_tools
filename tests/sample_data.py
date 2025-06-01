def get_header_compressed() -> bytes:
    with open("tests/files/header_compressed.bin", "rb") as file:
        return file.read()


def get_header_uncompressed() -> bytes:
    with open("tests/files/header_uncompressed.bin", "rb") as file:
        return file.read()


def get_header_fabricated() -> bytes:
    rec_version = b"\x01\x01\x01\x01\x00"
    checker = b"\x00\x00\x80\xBF"  # -1
    version_minor = b"\x02\x00"
    version_major = b"\x03\x00"
    build = b"\x04\x00\x00\x00"
    timestamp = b"\x05\x00\x00\x00"
    version = b"\x06\x00\x07\x00"
    internal_version = b"\x08\x00\x09\x00"
    data = b"\x0A\x0B\x0C\x0D\x0E\x0F"

    return rec_version + checker + version_minor + version_major + build + timestamp + version + internal_version + data


def get_postgame_fabricated() -> bytes:
    world_time_block = b"\x85\x30\x18\x00\x04\x00\x00\x00\x01\x00\x00\x00"
    leaderboards_block = b"\x01\x00\x00\x00\x03\x00\x00\x00\x01\x01\x02\x00\x00\x00\x00\x00\x00\x00\x6B\x09\x00\x00\x58\x06\x00\x00\x01\x00\x00\x00\x08\x08\x00\x00\x7E\x06\x00\x00\x26\x00\x00\x00\x02\x00\x00\x00"
    num_blocks = b"\x02\x00\x00\x00"
    version = b"\x01\x00\x00\x00"
    unknown = b"\xCE\xA4\x59\xB1\x05\xDB\x7B\x43"

    return world_time_block + leaderboards_block + num_blocks + version + unknown
