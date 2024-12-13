# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Define OutStreams for RAVEN workflows

  @author: Jacob Bryan (@j-bryan)
  @date: 2024-11-08
"""
from typing import Any
import xml.etree.ElementTree as ET

from ..xml_utils import find_node
from ..decorators import listproperty
from .base import RavenSnippet
from .dataobjects import DataObject


class OutStream(RavenSnippet):
  snippet_class = "OutStreams"

  @property
  def source(self) -> str | None:
    node = self.find("source")
    return None if node is None or not node.text else str(node.text)

  @source.setter
  def source(self, value: str | DataObject) -> None:
    find_node(self, "source").text = value

class PrintOutStream(OutStream):
  tag = "Print"

  def __init__(self, name: str | None = None) -> None:
    super().__init__(name)
    ET.SubElement(self, "type").text = "csv"  # The only supported output file type

  def add_parameter(self, name: str, value: Any) -> None:
    ET.SubElement(self, name).text = value

class OptPathPlot(OutStream):
  tag = "Plot"
  subtype = "OptPath"

  @listproperty
  def variables(self) -> list[str]:
    node = self.find("vars")
    return getattr(node, "text", []) or []

  @variables.setter
  def variables(self, value: list[str]) -> None:
    find_node(self, "vars").text = value

class HeronDispatchPlot(OutStream):
  tag = "Plot"
  subtype = "HERON.DispatchPlot"

  @property
  def macro_variable(self) -> str | None:
    node = self.find("macro_variable")
    return None if node is None else node.text

  @macro_variable.setter
  def macro_variable(self, value: str) -> None:
    find_node(self, "macro_variable").text = value

  @property
  def micro_variable(self) -> str | None:
    node = self.find("micro_variable")
    return None if node is None else node.text

  @micro_variable.setter
  def micro_variable(self, value: str) -> None:
    find_node(self, "micro_variable").text = value

  @listproperty
  def signals(self) -> list[str]:
    node = self.find("signals")
    return getattr(node, "text", []) or []

  @signals.setter
  def signals(self, value: list[str]) -> None:
    find_node(self, "signals").text = value

class TealCashFlowPlot(OutStream):
  """
  TEAL CashFlow plot
  """
  tag = "Plot"
  subtype = "TEAL.CashFlowPlot"
