import xml.etree.ElementTree as ET


class MockSnippet:
  def __init__(self, name=None, snippet_class=None, type=None):
    self.name = name or "some_name"
    self.snippet_class = snippet_class or "cls"
    self.type = type or "typ"

  def to_assembler_node(self, tag):
    node = ET.Element(tag, attrib={"class": self.snippet_class, "type": self.type})
    node.text = self.name
    return node

  def __repr__(self):
    return self.name


class MockSampledVariable:
  tag = "variable"
