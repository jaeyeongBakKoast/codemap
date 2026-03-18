# src/codemap/cli.py
import click


@click.group()
@click.version_option()
def main() -> None:
    """Codebase analysis and document generation tool."""


if __name__ == "__main__":
    main()
