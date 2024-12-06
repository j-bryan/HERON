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
    if len(vars) == 1 and isinstance(vars[0], list):
      vars = vars[0]
    new_vars = [v for v in vars if v not in self._variables]
    self._variables.extend(new_vars)
    self.text = self._variables
