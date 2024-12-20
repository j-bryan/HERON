"""
Alias types of major HERON classes for easier type hinting
"""
from typing import TypeAlias

# load utils
from .imports import Case, Placeholder, Component, ValuedParam

from .snippets import RavenSnippet

HeronCase: TypeAlias = Case
Source: TypeAlias = Placeholder

ListLike = list | tuple | set  # iterable but not a mapping (e.g. a dict) and not a string
