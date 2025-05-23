def get_header_compressed() -> bytes:
    with open("test/files/header_compressed.bin", "rb") as file:
        return file.read()


def get_header_uncompressed() -> bytes:
    with open("test/files/header_uncompressed.bin", "rb") as file:
        return file.read()
