import xml.etree.ElementTree as ET

from .base import RavenSnippet


class File(RavenSnippet):
  snippet_class = "Files"
  tag = "Input"

  def __init__(self, name: str | None = None, type: str | None = None) -> None:
    super().__init__(name)
    if type is not None:
      self.set("type", type)

  def to_assembler_node(self, tag: str) -> ET.Element:
    node = super().to_assembler_node(tag)
    # Type is set as a node attribute and is not the main node tag, in this case
    node.set("type", self.type)  # Need empty string for type if not set when creating assembler node
    return node

  @property
  def type(self) -> str:
    return self.get("type", "")

  @type.setter
  def type(self, value: str) -> None:
    self.set("type", value)

  @property
  def path(self) -> str:
    return self.text or ""

  @path.setter
  def path(self, value: str) -> None:
    self.text = value
