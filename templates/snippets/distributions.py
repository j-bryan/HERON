import keyword
import re
import xml.etree.ElementTree as ET

from ..xml_utils import find_node
from .base import RavenSnippet


class Distribution(RavenSnippet):
  snippet_class = "Distributions"

  def __init__(self, name: str | None = None) -> None:
    super().__init__(name)


def distribution_class_from_spec(spec):
  """
  Make a new distribution classfrom .he RAVEN input spec for that class
  @ In, spec, RAVEN input spec
  @ Out, distribution, NewDistribution, the new distribution class
  """
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

  # It might be tempting to use this node_property function everywhere! I tried it, and here's why I reverted
  # to manually defining properties:
  #   1. Direct definition of properties in the classes they belong to make it very clear how the property
  #      is defined. This helps readability and maintainability.
  #   2. This function gets very complicated as options are added to it, and in a way that's not easy to read.
  #      Separate definitions means these options can be handled on a case-by-case basis.
  #   3. Linters don't pick up on what properties are available when they're added dynamically. Directly defining
  #      them with their classes make the developer experience better when using RavenSnippets when building
  #      templates.
  def node_property(cls: ET.Element, prop_name: str, node_tag: str | None = None):
    """
    Creates a class property that gets/sets a child node text value
    @ In, cls, ET.Element, the ET.Element class or a subclass of it
    @ In, prop_name, str, property name
    @ In, node_tag, str | None, optional, tag or path of the node the property is tied to (default=prop_name)
    @ Out, None
    """
    if node_tag is None:
      node_tag = prop_name

    def getter(self):
      node = self.find(node_tag)
      return None if node is None else node.text

    def setter(self, val):
      find_node(self, node_tag).text = val

    def deleter(self):
      if (node := self.find(node_tag)) is not None:
        self.remove(node)

    doc = f"Accessor property for '{node_tag}' node text"
    setattr(cls, prop_name, property(getter, setter, deleter, doc=doc))

  class NewDistribution(Distribution):
    tag = spec.getName()

  for subnode in spec.subs:
    subnode_tag = subnode.getName()
    prop_name = camel_to_snake(subnode_tag)
    # can't use name if it's in keywords.kwlist (reserved keywords), so add a trailing underscore to the name
    if prop_name in keyword.kwlist:
      prop_name += "_"
    # Create a property to set the distribution parameters as "distribution.prop_name = value". This lets us keep a
    # property-based interface like our other snippet classes.
    node_property(NewDistribution, prop_name, subnode_tag)

  return NewDistribution
