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
def main(input: str, output: str):
    """Summary

    Args:
        input (str): Input file name
        output_file_name (str): Output file name
    """
    file = RecFile.parse(input)
    file.anonymize()
    file.write(output)


if __name__ == "__main__":
    main()
