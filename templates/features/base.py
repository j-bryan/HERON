from typing import Any
from abc import abstractmethod
import xml.etree.ElementTree as ET


class Feature:
  @abstractmethod
  def edit_template(self, template, case, components, sources) -> None:
    pass


class FeatureCollection(Feature):
  """
  Groups Feature objects together to define more complex features. Useful for grouping together
  features which are commonly used together, handling entity creation and entity settings
  separately, and more!
  """
  def __init__(self):
    self._features = []  # list[Feature]

  def edit_template(self, template, case, components, sources):
    for feature in self._features:
      feature.edit_template(template, case, components, sources)


class Entity:
  def __init__(self, name: str, class_name: str, type_name: str, subtype_name: str = "", settings: dict[str, Any] = {}) -> None:
    """
    @ In, name, str, the name of the entity
    @ In, class_name, str, the name of the class the entity belongs too (e.g. Models, Optimizers, DataObjects)
    @ In, type_name, str, the entity's type (e.g. Code, ROM, PointSet)
    @ In, subtype_name, str, optional, the entity's subtype (e.g. RAVEN as a subtype of Code)
    @ In, settings, dict[str, Any], optional, keyword settings which are added as XML child nodes
    @ Out, None
    """
    self._name = name
    self._class = class_name
    self._type = type_name
    self._subtype = subtype_name
    self._settings = settings

  def get_name(self) -> str:
    return self._name

  def get_class(self) -> str:
    return self._class

  def get_type(self) -> str:
    return self._type

  def get_subtype(self) -> str:
    return self._subtype

  def add_settings(self, settings: dict[str, Any] = {}, **kwargs) -> None:
    """
    Add settings by either providing a dict or keyword arguments.
    @ In, settings, dict[str, Any], optional, dict with new key-value settings pairs
    @ In, kwargs, dict, optional, new settings provided as keyword arguments
    @ Out, None
    """
    self._settings.update(settings)
    self._settings.update(kwargs)

  def to_xml(self) -> ET.Element:
    """
    Represent the Entity object in an XML format
    @ In, None
    @ Out, node, ET.Element, the entity XML node
    """
    # Gather name (required) and subtype (optional) attributes
    attrib = {"name": self.get_name()}
    if subtype := self.get_subtype():
      attrib["subType"] = subtype

    # Create new node for entity
    node = ET.Element(tag=self.get_type(), attrib=attrib)

    # Add settings key-value pairs as child nodes.
    # NOTE: _add_value_to_xml is recursive and can populate subtrees when the _settings[key] value is a dict or Entity
    for tag, value in self._settings.items():
      self._add_value_to_xml(node, tag, value)

    return node

  def _add_value_to_xml(self, parent: ET.Element, tag: str, value: Any) -> None:
    """
    Recursively build out entity subtree. Recurse over dicts, set child node text to string or numeric values,
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
    elif isinstance(value, Entity):
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
          self._value_to_xml(child, tag, value)
      elif hasattr(value, "__iter__") and not isinstance(value, str):
        child.text = ", ".join(value)
      else:
        child.text = value
