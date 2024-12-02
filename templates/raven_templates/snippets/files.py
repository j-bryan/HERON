import xml.etree.ElementTree as ET
from .base import RavenSnippet


class File(RavenSnippet):
  def __init__(self, tag: str, name: str, type: str = "") -> None:
    super().__init__(tag, name, "Files")
    self.set("type", type)

  @classmethod
  def from_xml(cls, node: ET.Element) -> "File":
    tag = node.tag
    name = node.get("name")
    file_type = node.get("type", "")
    file = cls(tag, name, file_type)
    return file

  def to_assembler_node(self, tag: str) -> ET.Element:
    node = ET.Element(tag)
    node.set("class", self.snippet_class)
    node.set("type", self.type)
    node.text = self.name
    return node
