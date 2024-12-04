# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Define OutStreams for RAVEN workflows

  @author: Jacob Bryan (@j-bryan)
  @date: 2024-11-08
"""
from typing import Any
import xml.etree.ElementTree as ET

from ..xml_utils import _to_string
from .base import RavenSnippet
from .dataobjects import DataObject


class OutStream(RavenSnippet):
  snippet_class = "OutSteams"

  def __init__(self, name: str):
    super().__init__(name)
    ET.SubElement(self, "source")

  def set_source(self, source: DataObject) -> None:
    source = self.find("source")
    source.text = _to_string(source)

class PrintOutStream(OutStream):
  tag = "Print"

  def __init__(self, name: str) -> None:
    super().__init__(name)
    type_node = ET.SubElement(self, "type")
    type_node.text = "csv"

  def add_parameter(self, name: str, value: Any) -> None:
    node = ET.SubElement(self, name)
    node.text = value

class OptPathPlot(OutStream):
  tag = "Plot"
  subtype = "OptPath"

  def __init__(self, name: str):
    super().__init__(name)
    ET.SubElement(self, "vars")

  def set_vars(self, vars: str | list[str]):
    self.find("vars").text = _to_string(vars)

class HeronDispatchPlot(OutStream):
  tag = "Plot"
  subtype = "HERON.DispatchPlot"

  def __init__(self, name: str):
    super().__init__(name)
    ET.SubElement(self, "macro_variable")
    ET.SubElement(self, "micro_variable")
    ET.SubElement(self, "signals")

  def set_time_indices(self, macro: str, micro: str) -> None:
    self.find("macro_variable").text = macro
    self.find("micro_variable").text = micro

  def set_signals(self, signals: str | list[str]) -> None:
    self.find("signals").text = signals

class TealCashFlowPlot(OutStream):
  """
  TEAL CashFlow plot
  """
  tag = "Plot"
  subtype = "TEAL.CashFlowPlot"
