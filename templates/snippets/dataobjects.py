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
    if isinstance(inputs[0], list) and len(inputs) == 1:
      # A list got passed in instead of many positional arguments (no star used)
      inputs = inputs[0]
    self._inputs.extend(inputs)
    find_node(self, "Input").text = self._inputs

  def add_outputs(self, *outputs: str | VariableGroup) -> None:
    if isinstance(outputs[0], list) and len(outputs) == 1:
      # A list got passed in instead of many positional arguments (no star used)
      outputs = outputs[0]
    self._outputs.extend(outputs)
    find_node(self, "Output").text = self._outputs


class PointSet(DataObject):
  tag = "PointSet"


class HistorySet(DataObject):
  tag = "HistorySet"


class DataSet(DataObject):
  tag = "DataSet"

  def add_index(self, index_var: str, variables: str | list[str]) -> None:
    index = ET.SubElement(self, "Index", {"var": index_var})
    index.text = variables
