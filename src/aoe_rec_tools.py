import logging
import time
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
    help="Remove player chat in the rec file"
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
@click.option(
    "--profile",
    required=False,
    is_flag=True,
    help="Print execution time"
)
def main(input: str, output: str, remove_system_chat: bool, remove_player_chat: bool, debug: bool, profile: bool):
    """Summary

    Args:
        input (str): Input file name
        output (str): Output file name
        remove_system_chat (bool): Flag to remove system chat
        remove_player_chat (bool): Flag to remove player chat
        debug (bool): Flag for debug output
        profile (bool): Flag for performance profiling
    """
    logger = logging.getLogger(__name__)
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    start_time = time.perf_counter()

    try:
        file = RecFile.parse(input)
        file.anonymize(remove_system_chat, remove_player_chat)
        file.write(output)
    except Exception as e:
        logger.error(e)
        logger.debug("Exception while anonymizing", exc_info=True)

    if profile:
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        logger.info(f"Execution time: {elapsed_ms:.2f} ms")


if __name__ == "__main__":
    main()
