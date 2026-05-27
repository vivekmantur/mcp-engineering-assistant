"""Helpers for loading markdown resources from the resources package."""

from pathlib import Path


BASE_DIR = Path(__file__).parent


def load_resource(file_name: str):
    """Read a resource file from the local resources directory.

    Args:
        file_name: Name of the markdown resource file.

    Returns:
        The resource file contents as text.
    """

    file_path = BASE_DIR / file_name

    with open(file_path, "r", encoding="utf-8") as file:

        return file.read()
