import itertools
from dataclasses import dataclass
from typing import Any
import xml.etree.ElementTree as ET

from .types import HeronCase, Component


@dataclass(frozen=True)
class Statistic:
  """
  A dataclass for building statistic names and ET.Elements. Hopefully this helps cut down repeated parsing of variable
  names and statistis meta infofrom .ase.
  """
  name: str
  prefix: str
  threshold : str | None = None
  percent: str | None = None

  def to_metric(self, variable: str) -> str:
    """
    Get the name for this statistic of variable
    @ In, variable, str, the variable name (e.g. NPV)
    @ Out, varname, str, the name of a variable's statistic (e.g. mean_NPV)
    """
    param = self.threshold or self.percent  # threshold, percent, or None
    parts = [self.prefix, param, variable] if param else [self.prefix, variable]
    varname = "_".join(parts)
    return varname

  def to_element(self, variable: str) -> ET.Element:
    """
    Get the statistic as an ET.Element, as is given to BasicStatistics and EconomicRatio PostProcessor models
    @ In, variable, str, the variable name (e.g. NPV)
    @ Out, element, ET.Element, the variable statistic element
    """
    element = ET.Element(self.name, prefix=self.prefix)
    if self.threshold:
      element.set("threshold", self.threshold)
    if self.percent:
      element.set("percent", self.percent)
    element.text = variable
    return element

def get_statistics(stat_names: list[str], stat_meta: dict) -> list[Statistic]:
  """
  Create Statistic objects for each statistic in stat_names
  @ In, stat_names, list[str], names of statistics
  @ In, stat_meta, dict, statistics meta data
  @ Out, stats, list[Statistic], Statistic objects for each statistic of interest
  """
  stats = []

  for name in stat_names:
    meta = stat_meta[name]
    prefix = meta["prefix"]
    percent = meta.get("percent", None)
    if not isinstance(percent, list):
      percent = [percent]
    threshold = meta.get("threshold", None)
    if not isinstance(threshold, list):
      threshold = [threshold]

    for perc, thresh in itertools.product(percent, threshold):
      new_stat = Statistic(name=name, prefix=prefix, threshold=thresh, percent=perc)
      stats.append(new_stat)

  return stats

def get_result_stats(names: list[str], stats: list[str], case: HeronCase) -> list[str]:
  """
    Constructs the names of the statistics requested for output
    @ In, names, list[str], result metric names (economics, component activities)
    @ In, stats, list[str], statistic names
    @ In, case, HeronCase, defining Case instance
    @ In, naming_template, str, template for naming results statistics
    @ Out, names, list[str], list of names of statistics requested for output
  """
  stats_objs = get_statistics(stats, case.stats_metrics_meta)
  stat_names = [stat.to_metric(name) for stat, name in itertools.product(stats_objs, names)]
  return stat_names

def get_capacity_vars(components: list[Component], name_template, *, debug=False) -> dict[str, Any]:
  """
  Get dispatch variable names
  @ In, components, list[Component], list of HERON components
  @ In, name_template, str, naming template for dispatch variable name, expecting
                            keywords "component", "tracker", and "resource"
  @ Out, vars, dict, variable name-value pairs
  """
  vars = {}

  for component in components:
    name = component.name
    # treat capacity
    ## we just need to make sure everything we need gets into the dispatch ensemble model.
    ## For each interaction of each component, that means making sure the Function, ARMA, or constant makes it.
    ## Constantsfrom .uter (namely sweep/opt capacities) are set in the MC Samplerfrom .he outer
    ## The Dispatch needs infofrom .he Outer to know which capacity to use, so we can't pass itfrom .ere.
    capacity = component.get_capacity(None, raw=True)

    if capacity.is_parametric():
      cap_name = name_template.format(unit=name, feature='capacity')
      values = capacity.get_value(debug=debug)
      vars[cap_name] = values
    elif capacity.type in ['StaticHistory', 'SyntheticHistory', 'Function', 'Variable']:
      # capacity is limited by a signal, so it has to be handled in the dispatch; don't include it here.
      # OR capacity is limited by a function, and we also can't handle it here, but in the dispatch.
      pass
    else:
      raise NotImplementedError

  return vars

def get_component_activity_vars(components: list[Component], name_template: str) -> list[str]:
  """
  Get dispatch variable names
  @ In, components, list[Component], list of HERON components
  @ In, name_template, str, naming template for dispatch variable name, expecting
                            keywords "component", "tracker", and "resource"
  @ Out, vars, list[str], list of variable names
  """
  vars = []

  for component in components:
    name = component.name
    for tracker in component.get_tracking_vars():
      resource_list = sorted(list(component.get_resources()))
      for resource in resource_list:
        var_name = name_template.format(component=name, tracker=tracker, resource=resource)
        vars.append(var_name)

  return vars

def get_opt_objective(case: HeronCase) -> str:
  """
  Get the name of the optimization objective
  @ In, case, HeronCase, the HERON case object
  @ Out, objective, str, the name of the objective
  """
  # What statistic is used for the objective?
  opt_settings = case.get_optimization_settings()
  try:
    statistic = opt_settings["stats_metric"]["name"]
  except (KeyError, TypeError):
    # FIXME: What about cases with only 1 history (not statistical)?
    statistic = "expectedValue"  # default to expectedValue

  meta = case.stats_metrics_meta[statistic]
  stat_name = meta["prefix"]
  param = meta.get("percent", None) or meta.get("threshold", None)
  if isinstance(param, list):
    param = param[0]
  if param:
    stat_name += f"_{param}"

  # What variable does the metric act on?
  target_var, _ = case.get_opt_metric()
  target_var_output_name = case.economic_metrics_meta[target_var]["output_name"]

  objective = f"{stat_name}_{target_var_output_name}"
  return objective

def get_cashflow_names(components):
  """
    Loop through components and collect all the full cashflow names
    @ In, components, list, list of HERON Component instances for this run
    @ Out, cfs, list, list of cashflow full names e.g. {comp}_{cf}_CashFlow
  """
  cfs = []
  for comp in components:
    comp_name = comp.name
    for cashflow in comp.get_cashflows():
      # User has specified to leave this cashflow out of the NPV calculation. Skip it.
      if cashflow.is_npv_exempt():
        continue
      cf_name = cashflow.name
      name = f"{comp_name}_{cf_name}_CashFlow"
      cfs.append(name)
      if cashflow.get_depreciation() is not None:
        cfs.append(f"{comp_name}_{cf_name}_depreciation")
        cfs.append(f"{comp_name}_{cf_name}_depreciation_tax_credit")
  return cfs
