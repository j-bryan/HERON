"""
Alias types of major HERON classes for easier type hinting
"""
import sys
import os
from typing import TypeAlias

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
from HERON.src.Cases import Case
from HERON.src.Components import Component
from HERON.src.Placeholders import Placeholder
from HERON.src.ValuedParams import ValuedParam
sys.path.pop()

HeronCase: TypeAlias = Case
Source: TypeAlias = Placeholder
