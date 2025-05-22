import logging
import click

from rec_file import RecFile


__version__ = "0.1"


@click.command()
@click.version_option(__version__)
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
    "--remove-player-chat",
    required=False,
    is_flag=True,
    help="Remove player chat in the rec file. Warning: Might cause issues with certain characters in some languages"
)
@click.option(
    "--remove-system-chat",
    required=False,
    is_flag=True,
    help="Remove system chat in the rec file"
)
@click.option(
    "--debug",
    required=False,
    is_flag=True,
    help="Enable debug logging"
)
def main(input: str, output: str, remove_system_chat: bool, remove_player_chat: bool, debug: bool):
    """Summary

    Args:
        input (str): Input file name
        output (str): Output file name
    """
    logger = logging.getLogger(__name__)
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s - %(message)s")

    try:
        file = RecFile.parse(input)
        file.anonymize(remove_system_chat, remove_player_chat)
        file.write(output)
    except Exception as e:
        logger.error(e)
        logger.debug("Exception while anonymizing", exc_info=True)


if __name__ == "__main__":
    main()
