import xml.etree.ElementTree as ET
from .base import RavenSnippet, attrib_property


class File(RavenSnippet):
  snippet_class = "Files"
  tag = "Input"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    attrib_property(cls, "type")

  def __init__(self, name: str, type: str | None = None) -> None:
    super().__init__(name)
    if type is not None:
      self.set("type", type)

  def to_assembler_node(self, tag: str) -> ET.Element:
    node = ET.Element(tag)
    node.set("class", self.snippet_class)
    node.set("type", self.get("type", ""))  # Need empty string for type if not set when creating assembler node
    node.text = self.name
    return node
