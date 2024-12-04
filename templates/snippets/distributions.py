import keyword
import re

from .base import RavenSnippet, node_property


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
  subnodes = [sub.getName() for sub in spec.subs]

  class NewDistribution(Distribution):
    pass

  NewDistribution.tag = dist_name

  for subnode_tag in subnodes:
    prop_name = camel_to_snake(subnode_tag)
    # can't use name if it's in keywords.kwlist (reserved keywords), so add a trailing underscore to the name
    if prop_name in keyword.kwlist:
      prop_name += "_"
    # Create a property to set the distribution parameters as "distribution.prop_name = value". We don't really
    # need to do this, but it gives us a nice interface.
    node_property(NewDistribution, prop_name, subnode_tag)

  return NewDistribution
