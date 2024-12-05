# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Define OutStreams for RAVEN workflows

  @author: Jacob Bryan (@j-bryan)
  @date: 2024-11-08
"""
from typing import Any
import xml.etree.ElementTree as ET

from ..utils import node_property

from .base import RavenSnippet
from .dataobjects import DataObject


class OutStream(RavenSnippet):
  snippet_class = "OutStreams"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    node_property(cls, "source")

  def __init__(self, name: str):
    super().__init__(name)

class PrintOutStream(OutStream):
  tag = "Print"

  def __init__(self, name: str) -> None:
    super().__init__(name)
    ET.SubElement(self, "type").text = "csv"

  def add_parameter(self, name: str, value: Any) -> None:
    node = ET.SubElement(self, name)
    node.text = value

class OptPathPlot(OutStream):
  tag = "Plot"
  subtype = "OptPath"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    node_property(cls, "variables", "vars")

class HeronDispatchPlot(OutStream):
  tag = "Plot"
  subtype = "HERON.DispatchPlot"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    node_property(cls, "macro_variable")
    node_property(cls, "micro_variable")
    node_property(cls, "signals")

class TealCashFlowPlot(OutStream):
  """
  TEAL CashFlow plot
  """
  tag = "Plot"
  subtype = "TEAL.CashFlowPlot"
