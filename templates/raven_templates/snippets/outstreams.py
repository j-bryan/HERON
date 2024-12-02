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
  def __init__(self, tag: str, name: str, subtype_name=None):
    super().__init__(tag, name, "OutStreams", subtype_name)
    self.source = ET.SubElement(self, "source")

  def set_source(self, source: DataObject) -> None:
    self.source.text = _to_string(source)

class PrintOutStream(OutStream):
  def __init__(self, name: str, **kwargs) -> None:
    super().__init__("Print", name)
    type_node = ET.SubElement(self, "type")
    type_node.text = "csv"

  def add_parameter(self, name: str, value: Any) -> None:
    node = ET.SubElement(self, name)
    node.text = value

class OptPathPlot(OutStream):
  def __init__(self, name="opt_path"):
    super().__init__("Plot", name, "OptPath")
    self.append(ET.Element("vars"))

  def set_vars(self, vars: str | list[str]):
    self.find("vars").text = _to_string(vars)

class HeronDispatchPlot(OutStream):
  def __init__(self, name="dispatch_plot"):
    super().__init__("Plot", name, "HERON.DispatchPlot")
    self.macro = ET.SubElement(self, "macro_variable")
    self.micro = ET.SubElement(self, "micro_variable")
    self.signals = ET.SubElement(self, "signals")

  def set_time_indices(self, macro: str, micro: str) -> None:
    self.macro = macro
    self.micro = micro

  def set_signals(self, signals: str | list[str]) -> None:
    self.signals.text = _to_string(signals)

class TealCashFlowPlot(OutStream):
  """
  TEAL CashFlow plot
  """
  def __init__(self, name="cashflow_plot"):
    super().__init__(name, "TEAL.CashFlowPlot")
