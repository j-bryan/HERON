from typing import Any
import inspect
import xml.etree.ElementTree as ET

from ..xml_utils import find_node


def node_property(cls: ET.Element, prop_name: str, node_tag: str | None = None, default=None):
  """
  Creates a class property that gets/sets a child node text value
  @ In, cls, ET.Element, the ET.Element class or a subclass of it
  @ In, prop_name, str, property name
  @ In, node_tag, str | None, optional, tag or path of the node the property is tied to (default=prop_name)
  @ In, default, Any, optional, the default getter value
  @ Out, None
  """
  if node_tag is None:
    node_tag = prop_name

  def getter(self):
    node = self.find(node_tag)
    return default if node is None else node.text

  def setter(self, val):
    find_node(self, node_tag).text = val

  setattr(cls, prop_name, property(getter, setter))


def attrib_property(cls: ET.Element, prop_name: str, attrib_name: str | None = None, default=None):
  """
  Creates a class property that gets/sets a node attribute value
  @ In, cls, ET.Element, the ET.Element class or a subclass of it
  @ In, prop_name, str, property name
  @ In, attrib_name, str | None, optional, name of the node attribute the property is tied to (default=prop_name)
  @ In, default, Any, optional, the default getter value
  @ Out, None
  """
  if attrib_name is None:
    attrib_name = prop_name

  def getter(self):
    return self.get(prop_name, default)

  def setter(self, val):
    self.set(prop_name, val)

  setattr(cls, prop_name, property(getter, setter))


class RavenSnippet(ET.Element):
  """
  RavenSnippet class objects describe one contiguous snippet of RAVEN XML, inheriting from the xml.etree.ElementTree.Element
  class. This base class contains methods for quickly building subtrees and set and access common RAVEN node attributes.
  """
  tag = None  # XML tag associated with the snippet class
  snippet_class = None  # class of Entity described by the snippet (e.g. Models, Optimizers, Samplers, DataObjects, etc.)
  subtype = None  # subtype of the snippet entity, does not need to be defined for all snippets

  @classmethod
  def _create_accessors(cls):
    """
    A shorthand for creating class properties to get and set node attributes and subnode text
    @ In, None
    @ Out, None
    """
    attrib_property(cls, "name")
    attrib_property(cls, "subtype", "subType")

  def __init__(self,
               name: str | None = None,
               subelements: dict[str, Any] = {},
               **kwargs) -> None:
    """
    @ In, name, str, the name of the entity
    @ In, subelements, dict[str, Any], optional, keyword settings which are added as XML child nodes
    @ In, kwargs, dict, optional, additional keyword arguments added to the Element attributes
    @ Out, None
    """
    super().__init__(self.tag)
    self._create_accessors()

    # Update node attributes with provided values
    # Arguments "name", "class_name", and "subtype_name" help to alias the problematic "class" attribute name and provide
    # an easy interface to set the common attributes "name" and "subType".
    if name is not None:
      self.attrib["name"] = name
    if self.subtype is not None:
      self.attrib["subType"] = self.subtype
    self.attrib.update(kwargs)

    self.add_subelements(subelements)

  def __repr__(self) -> str:
    """
    Make a string representation of the snippet. If the "name" attribute is defined, return that. Otherwise, fall back
    to the ET.Element implementation.
    """
    if name := self.name:
      return name
    return super().__repr__()

  @classmethod
  def from_xml(cls, node: ET.Element) -> "RavenSnippet":
    """
    Alternate constructor which instantiates a new RavenSnippet object from an existing XML node
    @ In, node, ET.Element, the template node
    @ Out, snippet, RavenSnippet, the new snippet
    """
    # Default implementation is to copy everything from the existing node into a new RavenSnippet object.
    # Looking at the class __init__ method signature can help us get the arguments right, such as getting the "name" attribute
    # from the XML node and passing that to the class constructor.
    init_signature = inspect.signature(cls.__init__)
    init_params = {k: node.get(k, v.default) for k, v in init_signature.parameters.items()}  # first argument is "self"; skip it
    init_params.pop("self")
    snippet = cls(**init_params)
    snippet.attrib.update(node.attrib)
    snippet.text = node.text
    for child in node:
      snippet.append(child)
    return snippet

  # # Attribute accessors
  # @property
  # def name(self) -> str:
  #   return self.attrib.get("name", "")

  # Subtree building utilities
  def add_subelements(self, subelements: dict[str, Any] = {}, **kwargs) -> None:
    """
    Add subelements by either providing a dict or keyword arguments.
    @ In, subelements, dict[str, Any], optional, dict with new key-value settings pairs
    @ In, kwargs, dict, optional, new settings provided as keyword arguments
    @ Out, None
    """
    parent = kwargs.pop("parent", self)
    for tag, value in (subelements | kwargs).items():
      self._add_subelement(parent, tag, value)

  def _add_subelement(self, parent: ET.Element, tag: str, value: Any) -> None:
    """
    Recursively build out subtree. Recurse over dicts, set child node text to string or numeric values,
    or form comma separated lists for other iterative data types (list, numpy array, tuple, set, etc.).
    @ In, parent, ET.Element, the parent node to append to
    @ In, tag, str, the tag of the child node
    @ In, value, Any, the value of the child node
    """
    # If the value inherits from ET.Element, we can append the value to the parent directly.
    if isinstance(value, ET.Element):
      parent.append(value)
    # If the value happens to be another entity, it has its own to_xml method. Use that instead of manually
    # using the tag input to create the child node.
    elif isinstance(value, RavenSnippet):
      # has a to_xml method
      child = value.to_xml()
      parent.append(child)
    # Otherwise, we'll create the child node ourselves. We handle several possible types of value:
    #   1. If value is a dict, create an XML subtree using the dict key-value pairs.
    #   2. If the value is iterable but not a string (so a list, numpy array, tuple, set, etc.), create a
    #      comma separated list of the values and set the node's text to that.
    #   3. If the value is anything else (assumes can be cast to a reasonable string), just set the node
    #      text to that value.
    else:
      child = ET.SubElement(parent, tag)
      if isinstance(value, dict):
        for tag, value in value.items():
          self._add_subelement(child, tag, value)
      else:
        child.text = value

  # Other utility functions
  def to_assembler_node(self, tag: str) -> ET.Element:
    """
    Creates an assembler node from the snippet, if possible. The "class" attribute must be defined.
    @ In, tag, str, assembler node tag
    """
    if not (self.snippet_class and self.name):
      raise ValueError("The RavenSnippet object cannot be expressed as an Assembler node! The object must have "
                       "'name' and 'class' attributes defined to create an Assembler node. Current values: "
                       f"class='{self.snippet_class}', name='{self.name}'.")

    node = ET.Element(tag)
    node.attrib["class"] = self.snippet_class
    node.attrib["type"] = self.tag
    node.text = self.name

    return node
