import itertools
from dataclasses import dataclass
from typing import Any
import xml.etree.ElementTree as ET

from .types import HeronCase


@dataclass(frozen=True)
class Statistic:
  """
  A dataclass for building statistic names and ET.Elements. Hopefully this helps cut down repeated parsing of variable
  names and statistis meta info from case.
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

def get_stat_prefixes(stat_names: list[str], case) -> list[str]:
  """
  Get all statistics prefixes for a list of statistic names
  @ In, stat_names, list[str], names of statistics
  @ In, case, Case, HERON case
  @ Out, stat_prefixes, list[str], list of statistics prefixes
  """
  stat_prefixes = []
  for stat in stat_names:
    stat_meta = case.stats_metrics_meta[stat]
    prefix = stat_meta["prefix"]

    # Are there additional attributes? If so, we need to loop over these.
    stat_attribs = {k: stat_meta[k] for k in stat_meta.keys() & {"percent", "threshold"}}

    if not stat_attribs:
      stat_prefixes.append(prefix)
    else:
      for val in stat_attribs.values():
        if isinstance(val, list):
          stat_prefixes.extend([f"{prefix}_{v}" for v in val])
        else:
          stat_prefixes.append(f"{prefix}_{val}")

  return stat_prefixes

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

def get_capacity_vars(components, name_template, *, debug=False) -> dict[str, Any]:
  """
  Get dispatch variable names
  @ In, components, list, list of HERON components
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
    ## Constants from outer (namely sweep/opt capacities) are set in the MC Sampler from the outer
    ## The Dispatch needs info from the Outer to know which capacity to use, so we can't pass it from here.
    capacity = component.get_capacity(None, raw=True)

    if capacity.is_parametric():
      cap_name = name_template.format(unit=name, feature='capacity')
      values = capacity.get_value(debug=debug)
      if isinstance(values, list) and debug:  # no debug value was provided, so use the first in the list
        values = values[0]
      vars[cap_name] = values
    elif capacity.type in ['StaticHistory', 'SyntheticHistory', 'Function', 'Variable']:
      # capacity is limited by a signal, so it has to be handled in the dispatch; don't include it here.
      # OR capacity is limited by a function, and we also can't handle it here, but in the dispatch.
      pass
    else:
      raise NotImplementedError

  return vars

def get_component_activity_vars(components: list, name_template: str) -> list[str]:
  """
  Get dispatch variable names
  @ In, components, list, list of HERON components
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
