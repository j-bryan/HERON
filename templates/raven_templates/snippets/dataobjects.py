import xml.etree.ElementTree as ET

from .base import RavenSnippet
from .variablegroups import VariableGroup


class DataObject(RavenSnippet):
  def __init__(self, tag: str, name: str) -> None:
    super().__init__(tag, name, "DataObjects")
    ET.SubElement(self, "Input")
    ET.SubElement(self, "Output")

  @classmethod
  def from_xml(cls, node: ET.Element) -> "DataObject":
    data = RavenSnippet.from_xml(node)
    data.snippet_class = cls.__name__
    return data

  def set_inputs(self, inputs: str | VariableGroup | list[str | VariableGroup]) -> None:
    inputs_node = self.find("Input")
    inputs_node.text = inputs

  def set_outputs(self, outputs: str | VariableGroup | list[str | VariableGroup]) -> None:
    outputs_node = self.find("Output")
    outputs_node.text = outputs


class PointSet(DataObject):
  def __init__(self, name: str) -> None:
    super().__init__("PointSet", name)


class HistorySet(DataObject):
  def __init__(self, name: str) -> None:
    super().__init__("HistorySet", name)


class DataSet(DataObject):
  def __init__(self, name: str) -> None:
    super().__init__("DataSet", name)

  def add_index(self, index_var: str, variables: str | list[str]) -> None:
    index = ET.SubElement(self, "Index", {"var", index_var})
    index.text = variables
