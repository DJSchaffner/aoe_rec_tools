import click

from rec_file import RecFile


@click.command()
@click.option(
    "-i", "--input",
    required=True,
    type=click.Path(exists=True, readable=True),
    help="Set input file name"
)
@click.option(
    "-o", "--output",
    required=False,
    type=click.Path(exists=False),
    default="out.aoe2record",
    help="Set output file name"
)
@click.option(
    "--keep-chat", "keep_chat",
    required=False,
    type=click.BOOL,
    default=False,
    help="Keeps the chat in the rec file. Warning: Might cause issues with certain characters in some languages"
)
def main(input: str, output: str, keep_chat: bool):
    """Summary

    Args:
        input (str): Input file name
        output (str): Output file name
    """
    try:
        file = RecFile.parse(input)
        file.anonymize(keep_chat)
        file.write(output)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
