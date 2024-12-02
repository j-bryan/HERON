import bisect
import xml.etree.ElementTree as ET

from .base import RavenSnippet


class VariableGroup(RavenSnippet):
  """ A group of variable names """
  def __init__(self, name: str) -> None:
    super().__init__("Group", name, "VariableGroups")
    self._variables = []  # list[str]

  @classmethod
  def from_xml(cls, node: ET.Element) -> "VariableGroup":
    vargroup = RavenSnippet.from_xml(node)
    vargroup.snippet_class = "VariableGroup"
    if vargroup.text:
      vargroup.add_variable(*[varname.strip() for varname in node.text.split(",")])
    return vargroup

  def add_variable(self, *vars: str) -> None:
    # Short-circuit for variable groups with empty variables list since there's no reason to
    # go through the expense of adding these one by one
    if len(self._variables) == 0:
      self._variables = sorted(vars)
      return

    # Insert the new variable names into the alphabetically sorted list
    for v in vars:
      bisect.insort(self._variables, v)
    self.text = self._variables
