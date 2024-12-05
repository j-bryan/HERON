import bisect
import xml.etree.ElementTree as ET

from .base import RavenSnippet


class VariableGroup(RavenSnippet):
  """ A group of variable names """
  snippet_class = "VariableGroups"
  tag = "Group"

  def __init__(self, name: str) -> None:
    super().__init__(name)
    self._variables = []  # list[str]

  @classmethod
  def from_xml(cls, node: ET.Element) -> "VariableGroup":
    vargroup = cls(node.get("name"))
    if node.text:
      vars = [varname.strip() for varname in node.text.split(",")]
      vargroup.add_variables(*vars)
    return vargroup

  def add_variables(self, *vars: str) -> None:
    self._variables.extend(vars)
    self.text = self._variables
