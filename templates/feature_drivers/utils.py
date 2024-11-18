from typing import Any
import xml.etree.ElementTree as ET


def add_to_comma_separated_list(s, val):
  if s:
    s += ", " + val
  else:
    return val

def add_step_to_sequence(template, step):
  sequence = template.find("RunInfo/Sequence")
  steps = sequence.text
  if steps:
    steps += ", " + step
  else:
    steps = step
  sequence.text = steps

def build_opt_metric_from_name(case) -> str:
  """
    Constructs the output name of the metric specified as the optimization objective. If no metric was
    provided in the HERON XML, this defaults to "mean_NPV".
    @ In, case, HERON Case, defining Case instance
    @ Out, opt_out_metric_name, str, output metric name for use in inner/outer files
  """
  try:
    # metric name in RAVEN
    optimization_settings = case.get_optimization_settings()
    metric_raven_name = optimization_settings['stats_metric']['name']
    # potential metric name to add
    opt_out_metric_name = case.stats_metrics_meta[metric_raven_name]['prefix']
    # do I need to add a percent or threshold to this name?
    if metric_raven_name == 'percentile':
      opt_out_metric_name += '_' + str(optimization_settings['stats_metric']['percent'])
    elif metric_raven_name in ['valueAtRisk', 'expectedShortfall', 'sortinoRatio', 'gainLossRatio']:
      opt_out_metric_name += '_' + str(optimization_settings['stats_metric']['threshold'])
    opt_econ_metric, _ = case.get_opt_metric()
    output_econ_metric_name = case.economic_metrics_meta[opt_econ_metric]['output_name']
    opt_out_metric_name += f'_{output_econ_metric_name}'
  except (TypeError, KeyError):
    # <optimization_settings> node not in input file OR
    # 'metric' is missing from _optimization_settings
    opt_out_metric_name = "mean_NPV"

  return opt_out_metric_name

def get_feature_list(case, components) -> list[str]:
  # TODO there must be a better way
  feature_list = []
  for component in components:  # get all interaction capacities which are features
    interaction = component.get_interaction()
    cap = interaction.get_capacity(None, raw=True)
    if cap.is_parametric() and isinstance(cap.get_value(debug=case.debug['enabled']) , list):
      feature_list.append(component.name + '_capacity')
  return feature_list
