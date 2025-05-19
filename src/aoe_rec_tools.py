import sys
from getopt import getopt

from rec_file import RecFile


def print_usage():
    print(
        "Usage: aoe_rec_tools.py [OPTIONS]\n"
        "OPTIONS:\n"
        "    -i Input file"
    )


def main():
    opts, _ = getopt(sys.argv[1:], "hi:", ["help", "input="])
    rec_file = None

    for opt, arg in opts:
        match opt:
            case "-h" | "--help":
                print_usage()
                sys.exit()
            case "-i" | "--input":
                rec_file = arg.strip()
            case _:
                print(f"Unhandled option: {opt}")

    if rec_file is None:
        print("No rec file given")
        sys.exit()

    file = RecFile.parse(rec_file)
    file.anonymize()
    file.write("out.aoe2record")


if __name__ == "__main__":
    main()
