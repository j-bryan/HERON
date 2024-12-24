# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  File snippets

  @author: Jacob Bryan (@j-bryan)
  @date: 2024-11-08
"""
import xml.etree.ElementTree as ET

from .base import RavenSnippet


class File(RavenSnippet):
  """ Snippet class for input files """
  snippet_class = "Files"
  tag = "Input"

  # def __init__(self, name: str | None = None, type: str | None = None) -> None:
  #   """
  #   Constructor
  #   @ In, name, str, optional, the file name
  #   @ In, type, str, optional, the file type
  #   @ Out, None
  #   """
  #   super().__init__(name)
  #   # The type attribute requires some
  #   if type is not None:
  #     self.set("type", type)

  def to_assembler_node(self, tag: str) -> ET.Element:
    node = super().to_assembler_node(tag)
    # Type is set as a node attribute and is not the main node tag, as is assumed in the default implementation.
    # The "type" attribute should be an empty string if not set.
    node.set("type", self.type or "")
    return node

  @property
  def type(self) -> str | None:
    """
    type getter
    @ In, None,
    @ Out, type, str | None, the file type
    """
    return self.get("type", None)

  @type.setter
  def type(self, value: str) -> None:
    """
    type setter
    @ In, value, str, the type value to set
    @ Out, None
    """
    self.set("type", str(value))

  @property
  def path(self) -> str | None:
    """
    file path getter
    @ In, None,
    @ Out, path, str | None, the file path
    """
    return self.text

  @path.setter
  def path(self, value: str) -> None:
    """
    file path setter
    @ In, value, str, the file path to set
    @ Out, None
    """
    self.text = str(value)
