import logging
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
@click.option(
    "--debug",
    required=False,
    is_flag=True,
    help="Enable debug logging"
)
def main(input: str, output: str, keep_system_chat: bool, keep_player_chat: bool, debug: bool):
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
        file.anonymize(keep_system_chat, keep_player_chat)
        file.write(output)
    except Exception as e:
        logger.error(e)
        logger.debug("Exception while anonymizing", exc_info=True)


if __name__ == "__main__":
    main()
