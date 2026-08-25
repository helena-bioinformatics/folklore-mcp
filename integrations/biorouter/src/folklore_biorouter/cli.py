"""Command-line entry point for the Biorouter bridge."""

from folklore_biorouter.server import create_server


def main() -> None:
    """Run the local stdio bridge expected by Biorouter."""
    create_server().run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
