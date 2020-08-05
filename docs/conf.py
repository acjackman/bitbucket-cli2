"""Sphinx configuration."""
from datetime import datetime


project = "BitBucket CLI"
author = "Adam Jackman"
copyright = f"{datetime.now().year}, {author}"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon"]
autodoc_typehints = "description"
