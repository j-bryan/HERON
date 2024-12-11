import xml.etree.ElementTree as ET

from .base import RavenSnippet
from ..decorators import listproperty


class VariableGroup(RavenSnippet):
  """ A group of variable names """
  snippet_class = "VariableGroups"
  tag = "Group"

  @classmethod
  def from_xml(cls, node: ET.Element) -> "VariableGroup":
    vargroup = cls(node.get("name"))
    if node.text:
      vars = [varname.strip() for varname in node.text.split(",")]
      vargroup.variables = vars
    return vargroup

  @listproperty
  def variables(self) -> list[str]:
    return self.text or []

  @variables.setter
  def variables(self, value: list[str]) -> None:
    self.text = value
