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
    "--keep-player-chat",
    required=False,
    is_flag=True,
    help="Keep player chat in the rec file. Warning: Might cause issues with certain characters in some languages"
)
@click.option(
    "--keep-system-chat",
    required=False,
    is_flag=True,
    help="Keep system chat in the rec file"
)
def main(input: str, output: str, keep_system_chat: bool, keep_player_chat: bool):
    """Summary

    Args:
        input (str): Input file name
        output (str): Output file name
    """
    try:
        file = RecFile.parse(input)
        file.anonymize(keep_system_chat, keep_player_chat)
        file.write(output)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
