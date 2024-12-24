import xml.etree.ElementTree as ET


class MockSnippet:
  name = None
  snippet_class = None
  tag = None

  def __init__(self, name=None, snippet_class=None, tag=None):
    self.name = name or "some_name"
    self.snippet_class = snippet_class or "cls"
    self.tag = tag or "some_tag"

  def to_assembler_node(self, tag):
    node = ET.Element(tag, attrib={"class": self.snippet_class, "type": self.tag})
    node.text = self.name
    return node

  def __repr__(self):
    return self.name


class MockSnippetBase:
  def __init__(self, snippet_class=None):
    self.tag = None
    self.snippet_class = snippet_class or "cls"


class MockSampledVariable:
  tag = "variable"
