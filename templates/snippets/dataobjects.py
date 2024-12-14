import xml.etree.ElementTree as ET

from ..xml_utils import find_node
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
    # Force to be a list
    if not isinstance(variables, list):
      variables = [str(variables)]

    # There shouldn't be any reason to have duplicate index nodes, so only add the indicated index variable
    index_node = self.find(f"Index[@var='{index_var}']")
    if index_node is None:
      ET.SubElement(self, "Index", {"var": index_var}).text = variables
    else:
      # If there are any variables provided that aren't in the existing index node's text, add them here.
      for var in variables:
        if var not in index_node.text:
          index_node.text.append(var)
