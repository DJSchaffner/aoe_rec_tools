def get_header_compressed() -> bytes:
    with open("test/files/header_compressed.bin", "rb") as file:
        return file.read()


def get_header_uncompressed() -> bytes:
    with open("test/files/header_uncompressed.bin", "rb") as file:
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
