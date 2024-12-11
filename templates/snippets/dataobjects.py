import xml.etree.ElementTree as ET

from ..utils import find_node
from ..decorators import listproperty
from .base import RavenSnippet


class DataObject(RavenSnippet):
  snippet_class = "DataObjects"

  @listproperty
  def inputs(self) -> list[str]:
    node = self.find("Input")
    return getattr(node, "text", []) or []

  @inputs.setter
  def inputs(self, value: list[str]) -> None:
    find_node(self, "Input").text = value

  @listproperty
  def outputs(self) -> list[str]:
    node = self.find("Output")
    return getattr(node, "text", []) or []

  @outputs.setter
  def outputs(self, value: list[str]) -> None:
    find_node(self, "Output").text = value


class PointSet(DataObject):
  tag = "PointSet"


class HistorySet(DataObject):
  tag = "HistorySet"


class DataSet(DataObject):
  tag = "DataSet"

  def add_index(self, index_var: str, variables: str | list[str]) -> None:
    ET.SubElement(self, "Index", {"var": index_var}).text = variables
