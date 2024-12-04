import sys
import os
import xml.etree.ElementTree as ET

from .base import RavenSnippet
from . import distributions

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
sys.path.pop()

RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))

sys.path.append(os.path.join(RAVEN_LOC, '..'))
from ravenframework.Distributions import returnInputParameter
sys.path.pop()


def get_all_subclasses(cls):
  """
    Recursively collect all of the classes that are a subclass of cls
    @ In, cls, the class to retrieve sub-classes.
    @ Out, getAllSubclasses, list of class objects for each subclass of cls.
  """
  return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in get_all_subclasses(s)]


class SnippetFactory:
  def __init__(self) -> None:
    self.registered_classes = {}  # dict[str, RavenSnippet]
    # NOTE: Keys for registered classes are formatted like XPaths. This functionality isn't currently used,
    # but could be useful, e.g. for finding any XML nodes which match a certain snippet class.

  def register_snippet_class(self, *cls: RavenSnippet) -> None:
    for snip_cls in cls:
      if not snip_cls.tag:  # base classes don't have tags defined; skip these
        continue

      key = self._get_snippet_class_key(snip_cls)

      # What if the key is already in the dict but there are
      if key in self.registered_classes and (existing_cls := self.registered_classes[key]) != snip_cls:
        raise ValueError("A key collision has occurred when registering a RavenSnippet class! "
                         f"Key: {key}, Class to add: {snip_cls}, Existing class: {existing_cls}")

      self.registered_classes[key] = snip_cls

  def register_all_subclasses(self, cls) -> None:
    self.register_snippet_class(*get_all_subclasses(cls))

  def from_xml(self, node: ET.Element) -> ET.Element:
    # Find the registered class which matches the tag and required attributes
    key = self._get_node_key(node)
    try:
      cls = self.registered_classes[key]
    except KeyError:
      # Not a registered type, so just toss the node back to the caller?
      return node

    snippet = cls.from_xml(node)
    return snippet

  def is_registered(self, node: ET.Element) -> bool:
    key = self._get_node_key(node)
    return key in self.registered_classes

  @staticmethod
  def _get_snippet_class_key(cls: RavenSnippet) -> str:
    key = f"{cls.tag}"
    # TODO: delineate snippet type by additional attributes?
    if cls.subtype is not None:
      key += f"[@subType='{cls.subtype}']"
    return key

  @staticmethod
  def _get_node_key(node: ET.Element) -> str:
    key = node.tag
    if subtype := node.get("subType", None):
      key += f"[@subType='{subtype}']"
    return key


# There are many allowable distributions, each of which have their own properties. Rather than manually create classes for those,
# we can read from the RAVEN distributions input specs and dynamically create RavenSnippet classes for those distributions.

dist_collection = returnInputParameter()
for sub in dist_collection.subs:
  # We create a new distribution class for every RAVEN distribution class in the RAVEN input spec, then register that new class
  # with the templates.snippets.distributions module so they can be imported as expected.
  dist_class = distributions.distribution_class_from_spec(sub)
  setattr(distributions, dist_class.tag, dist_class)


factory = SnippetFactory()
factory.register_all_subclasses(RavenSnippet)
