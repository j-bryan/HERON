import xml.etree.ElementTree as ET
from .base import RavenSnippet


class File(RavenSnippet):
  snippet_class = "Files"
  tag = "Input"

  def __init__(self, name: str, type: str | None = None) -> None:
    super().__init__(name)
    if type is not None:
      self.set("type", type)

  @property
  def type(self) -> str | None:
    return self.get("type", None)

  @type.setter
  def type(self, val: str) -> None:
    self.set("type", val)

  @classmethod
  def from_xml(cls, node: ET.Element) -> "File":
    name = node.get("name")
    file = cls(name)
    file.type = node.get("type", None)
    return file

  def to_assembler_node(self, tag: str) -> ET.Element:
    node = ET.Element(tag)
    node.set("class", self.snippet_class)
    node.set("type", self.get("type", ""))  # Need empty string for type if not set when creating assembler node
    node.text = self.name
    return node
