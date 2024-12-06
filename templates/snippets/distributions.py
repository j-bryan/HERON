import keyword
import re

from ..utils import node_property
from .base import RavenSnippet

import sys
import os

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
sys.path.pop()

RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))

sys.path.append(os.path.join(RAVEN_LOC, '..'))
from ravenframework.utils import xmlUtils
from ravenframework.InputTemplates.TemplateBaseClass import Template
from ravenframework.utils import InputTypes
sys.path.pop()

raven_types = {
  InputTypes.IntegerType: int,
  InputTypes.FloatType: float,
  InputTypes.StringType: str,
  InputTypes.BoolType: bool
}


class Distribution(RavenSnippet):
  snippet_class = "Distributions"

  def __init__(self, name: str) -> None:
    super().__init__(name)


def camel_to_snake(camel: str) -> str:
    """
    Converts camelCase to snake_case, handling grouped capital letters
    @ In, camel, str, a camel case string
    @ Out, snake, str, a snake case string
    """
    snake = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", camel)  # Handle grouped capitals
    snake = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", snake)  # Handle single capitals
    snake = snake.lower()
    return snake


def distribution_class_from_spec(spec):
  """
  Make a new distribution class from the RAVEN input spec for that class
  @ In, spec, RAVEN input spec
  @ Out, distribution, NewDistribution, the new distribution class
  """
  dist_name = spec.getName()

  class NewDistribution(Distribution):
    tag = dist_name

  for subnode in spec.subs:
    subnode_tag = subnode.getName()
    prop_name = camel_to_snake(subnode_tag)
    # can't use name if it's in keywords.kwlist (reserved keywords), so add a trailing underscore to the name
    if prop_name in keyword.kwlist:
      prop_name += "_"
    prop_type = raven_types.get(subnode.contentType, str)
    default = None if subnode.default == "no-default" else subnode.default
    # Create a property to set the distribution parameters as "distribution.prop_name = value". We don't really
    # need to do this, but it gives us a nice interface.
    node_property(NewDistribution, prop_name, subnode_tag, default=default, prop_type=prop_type)

  return NewDistribution
