import xml.etree.ElementTree as ET

from .base import RavenSnippet
from .variablegroups import VariableGroup

from ..xml_utils import find_node


class DataObject(RavenSnippet):
  snippet_class = "DataObjects"

  def __init__(self, name: str) -> None:
    super().__init__(name)
    self._inputs = []
    self._outputs = []

  def add_inputs(self, *inputs: str | VariableGroup) -> None:
    self._inputs.extend(inputs)
    input_node = find_node(self, "Input")
    input_node.text = self._inputs

  def add_outputs(self, *outputs: str | VariableGroup) -> None:
    self._outputs.extend(outputs)
    output_node = find_node(self, "Output")
    output_node.text = self._outputs


class PointSet(DataObject):
  tag = "PointSet"


class HistorySet(DataObject):
  tag = "HistorySet"


class DataSet(DataObject):
  tag = "DataSet"

  def add_index(self, index_var: str, variables: str | list[str]) -> None:
    index = ET.SubElement(self, "Index", {"var": index_var})
    index.text = variables
