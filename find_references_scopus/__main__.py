"""Entry point untuk `python -m find_references_scopus`.

Memanggil main() dari cli.py.
"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
