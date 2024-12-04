from typing import Any
import itertools


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


def get_result_stats(names: list[str], stats: list[str], case, naming_template: str):
  """
    Constructs the names of the statistics requested for output
    @ In, names, list[str], result metric names (economics, component activities)
    @ In, stats, list[str], statistic names
    @ In, case, HERON Case, defining Case instance
    @ In, naming_template, str, template for naming results statistics
    @ Out, names, list, list of names of statistics requested for output
  """
  stat_prefixes = get_stat_prefixes(stats, case)
  stat_names = [naming_template.format(prefix=prefix, name=name) for prefix, name in itertools.product(stat_prefixes, names)]
  return stat_names


def get_statistical_results_vars(case, components: list, default_stats: list[str], financial_stats: list[str], naming_templates: dict[str, str] = {}) -> list[str]:
  """
  Collects result metric names for statistical metrics
  @ In, case, Case, HERON case
  @ In, components, list[Component], HERON components
  @ Out, var_names, list[str], list of variable names
  """
  # Add statistics for economic metrics to variable group. Use all statistics.
  stats_names = set(default_stats) | set(case.get_result_statistics())
  econ_metrics = case.get_econ_metrics(nametype="output")
  stats_var_default_template = "{prefix}_{name}"
  stats_var_names = get_result_stats(econ_metrics, stats_names, case, naming_templates.get("statistic", stats_var_default_template))

  # Add total activity statistics for variable group. Use only non-financial statistics.
  non_fin_stat_names = stats_names - set(financial_stats)
  # tot_activity_metrics = self._get_activity_metrics(components)
  tot_act_default_template = "TotalActivity__{component}__{tracker}__{resource}"
  tot_activity_metrics = get_component_activity_vars(components, naming_templates.get("tot_activity", tot_act_default_template))
  activity_var_names = get_result_stats(tot_activity_metrics, non_fin_stat_names, case)

  var_names = stats_var_names + activity_var_names

  return var_names


def get_capacity_vars(components, name_template, debug=False) -> dict[str, Any]:
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
      # this capacity is being [swept or optimized in outer] (list) or is constant (float)
      # -> so add a node, put either the const value or a dummy in place
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
