# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Define plots for RAVEN workflows

  @author: Jacob Bryan (@j-bryan)
  @date: 2024-11-08
"""
from .feature_driver import FeatureDriver, FeatureCollection
from snippets import EntityNode, StepNode, AssemblerNode
from utils import add_step_to_sequence


class PlotBase(FeatureDriver):
  def __init__(self, name, source, subType):
    super().__init__()
    self._name = name
    self._subType = subType
    self._plot_params = {
      "source": source,
    }

  def _modify_outstreams(self, template, case, components, sources):
    # Create new <Plot> node for the dispatch plot
    plot = EntityNode("Plot", self._name, self._subType, self._plot_params)

    # Add plot to the OutStreams
    outstreams = template.find("OutStreams")
    outstreams.append(plot)

  def _modify_steps(self, template, case, components, sources):
    # Make IOStep for plot
    source = self.subs["source"]
    source_dataobj = template.find(f"DataObjects/[@name='{source}']")
    source_type = source_dataobj.tag
    source_name = source_dataobj.get("name")

    plot_input = AssemblerNode("Input", "DataObjects", source_type, source_name)
    plot_output = AssemblerNode("Output", "OutStreams", "Plot", self._name)
    plot_io = StepNode("IOStep", self._name, [plot_input, plot_output])

    steps = template.find("Steps")
    steps.append(plot_io)

  def _modify_runinfo(self, template, case, components, sources):
    # Add step to RunInfo sequnce
    # TODO: how to ensure the IOStep comes in appropriate order (e.g. after MultiRun)
    add_step_to_sequence(template, self._name)

class HeronDispatchPlot(PlotBase):
  def __init__(self, name="dispatch_plot", source="dispatch", subType="HERON.DispatchPlot"):
    super().__init__(name, source, subType)

  def edit_template(self, template, case, components, sources):
    self._plot_params["macro_variable"] = case.get_year_name()
    self._plot_params["micro_variable"] = case.get_time_name()

    # Which signals to plot?
    signals = set([src.get_variable() for src in sources])
    signals.discard(None)  # pop None from the set, if it's in there
    self._plot_params["signals"] = ", ".join(signals)

    super().edit_template(template, case, components, sources)


class TealCashFlowPlot(FeatureDriver):
  """
  TEAL CashFlow plot
  """
  def __init__(self, name="cashflow_plot", source="cashflows", subType="TEAL.CashFlowPlot"):
    super().__init__(self, name, source, subType)
