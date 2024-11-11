from feature_driver import FeatureCollection
from plots import HeronDispatchPlot, TealCashFlowPlot

class DebugPlots(FeatureCollection):
  """
  Debug mode plots
  """
  def edit_template(self, template, case, components, sources):
    """
    Edits the template in-place
    @ In, template
    @ In, case
    @ In, components
    @ In, sources
    """
    if case.debug["dispatch_plot"]:
      self._features.append(HeronDispatchPlot())
    if case.debug["cashflow_plot"]:
      self._features.append(TealCashFlowPlot())

    super().edit_template(template, case, components, sources)
