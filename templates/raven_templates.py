# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  RAVEN workflow templates

  @author: j-bryan
  @date: 2024-10-29
"""
import sys
import os
import xml.etree.ElementTree as ET

from .features.base import Feature
from .features.steps import Step, MultiRunStep, IOStep, PostProcessStep
from .features.samplers import GridSampler
from .features.optimizers import BayesianOptimizer, GradientDescentOptimizer

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from HERON.src.base import Base
from HERON.src.Cases import Case
from HERON.src.Components import Component
from HERON.src.Placeholders import ARMA, CSV
import HERON.src._utils as hutils
sys.path.pop()

RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))

sys.path.append(os.path.join(RAVEN_LOC, '..'))
from ravenframework.InputTemplates.TemplateBaseClass import Template
sys.path.pop()


class RavenTemplate(Template):
  """ Template class for RAVEN workflows """
  Template.addNamingTemplates({'jobname'        : '{case}_{io}',
                               'stepname'       : '{action}_{subject}',
                               'variable'       : '{unit}_{feature}',
                               'dispatch'       : 'Dispatch__{component}__{tracker}__{resource}',
                               'tot_activity'   :'{stats}_TotalActivity__{component}__{tracker}__{resource}',
                               'data object'    : '{source}_{contents}',
                               'distribution'   : '{unit}_{feature}_dist',
                               'ARMA sampler'   : '{rom}_sampler',
                               'lib file'       : 'heron.lib', # TODO use case name?
                               'cashfname'      : '_{component}{cashname}',
                               're_cash'        : '_rec_{period}_{driverType}{driverName}',
                               'cluster_index'  : '_ROM_Cluster',
                               'metric_name'    : '{stats}_{econ}',
                               })

  def __init__(self):
    super().__init__()
    self.features = []  # list[Feature], which features to add
    self.sequence = []  # list[Step], sequence of steps to set in RunInfo/Sequence block

  ######################
  # RAVEN Template API #
  ######################
  def loadTemplate(self):
    # TODO
    # load XML from file
    pass

  def createWorkflow(self, case: Case, components: list[Component], sources: list[CSV | ARMA]) -> "RavenTemplate":
    """
    Create workflow by applying feature changes to the template XML

    @ In, case, HERON.src.Cases.Case
    @ In, components, list[HERON.src.Components.Component]
    @ In, sources, TODO
    @ Out, None
    """
    self.set_features(case, components, sources)  # NOTE: Overwrite the set_features function in child classes
    for feature in self.features:
      feature.edit_template(self._template, case, components, sources)
    self.set_sequence()
    return self

  def writeWorkflow(self):
    # TODO
    pass

  ############################
  # XML manipulation methods #
  ############################
  def find(self, match: str, namespaces: str = None) -> ET.Element | None:
    """
    Find the first node with a matching tag or path in the template XML. Wraps the
    xml.etree.ElementTree.Element.find() method.

    @ In, match, str, string to match tag name or path
    @ In, namespaces, str, optional, an optional mapping form namespace prefix to full name
    @ Out, node, ET.Element | None, first element with matching tag or None if no matches are found
    """
    return self._template.find(match, namespaces)

  def findall(self, match: str, namespaces: str = None) -> list[ET.Element] | None:
    """
    Find all nodes  with a matching tag or path in the template XML. Wraps the
    xml.etree.ElementTree.Element.findall() method.

    @ In, match, str, string to match tag name or path
    @ In, namespaces, str, optional, an optional mapping form namespace prefix to full name
    @ Out, nodes, list[ET.Element] | None, first element with matching tag or None if no matches are found
    """
    return self._template.findall(match, namespaces)

  ################################
  # Feature modification methods #
  ################################
  def set_features(self, case, components, sources) -> None:
    """
    Sets a list of features based on case, component, and source information.

    @ In, case
    @ In, components,
    @ In, sources,
    @ Out, None
    """
    # In this RavenTemplate parent class, apply any edits which apply to all RAVEN templates
    # TODO: RunInfo block edits?
    pass

  def set_sequence(self) -> None:
    # TODO: validate/determine sequence based on operations with DataObjects?
    sequence = self.find("RunInfo/Sequence")
    sequence.text = ", ".join([step.get_name() for step in self.sequence])

# Templates for specific workflow types
class OneHistoryTemplate(Template):
  pass

class DispatchTemplate(Template):
  pass

class BilevelOuterTemplate(Template):
  Template.addNamingTemplate({
    "optimizer": "cap_opt",
    "model": "raven"
  })

  def set_features(self, case, components, sources) -> None:
    """
    Sets a list of features based on case, component, and source information.

    @ In, case
    @ In, components,
    @ In, sources,
    @ Out, None
    """
    super().set_features(case, components, sources)
    if case.get_mode() == "sweep":
      self._set_sweep_features(case, components, sources)
    elif case.get_mode() == "opt":
      self._set_opt_features(case, components, sources)
    else:
      # Shouldn't ever reach here
      raise ValueError(f"Unknown case mode '{case.get_mode()}'. Must be one of ['sweep', 'opt'].")

  def _set_sweep_features(self, case, components, sources) -> None:
    # - Sweep data objects: grid
    grid = PointSet("grid")
    # - Sweep outstream print
    sweep_print = PrintOutStream("sweep", grid)
    # - Grid sampler (make interchangeable??)
    sampler = GridSampler("grid")
    # - Sweep multirun
    multirun = MultiRunStep("sweep")
    # - Print iostep
    print_step = IOStep("print", sweep_print)

    # Add features to the template's self.features list
    sweep_features = [grid, sweep_print, sampler, multirun, sweep_print]
    self.features.extend(sweep_features)
    self.sequence.extend([multirun, sweep_print])

  def _set_opt_features(self, case, components, sources) -> None:
    # - Optimizer DataObjects: opt_eval, opt_soln
    opt_eval = PointSet("opt_eval")
    opt_soln = PointSet("opt_soln")
    # - Optimizer OutStreams: opt_soln print, opt_soln plot
    opt_soln_print = PrintOutStream("opt_soln", opt_soln)
    opt_path_plot = PlotOutStream("opt_path", opt_soln)
    # - Optimizer settings
    #     - BO: BO optimizer, stratified sampler, GP ROM
    #     - GD: GD optimizer
    if case.get_opt_strategy() == "BayesianOpt":
      optimizer = BayesianOptimizer("cap_opt")
    elif case.get_opt_strategy() == "GradientDescent":
      optimizer = GradientDescent("cap_opt")
    else:
      raise ValueError(f"Unrecognized optimization strategy {case.get_opt_strategy()}.")
    #     - OptimizationSettings handed to either optimizer to fill out common settings
    opt_settings = OptimizationSettings(optimizer="cap_opt")
    # - Optimize multirun
    multirun = MultiRunStep("optimize")  # add model, optimizer, etc.
    # - Output IOSteps
    print_step = IOStep("print", opt_soln_print)
    plot_step = IOStep("plot", opt_path_plot)

    opt_features = [opt_eval, opt_soln, opt_soln_print, opt_path_plot,
                    optimizer, opt_settings, multirun, print_step, plot_step]
    self.features.extend(opt_features)
    self.sequence.extend([multirun, print_step, plot_step])


class BilevelInnerTemplate(Template):
  Template.addNamingTemplates({"model_name": "dispatch",
                               "sampler_name": "sampler"})

  def set_features(self, case, components, sources) -> None:
    """
    Sets a list of features based on case, component, and source information.

    @ In, case
    @ In, components,
    @ In, sources,
    @ Out, None
    """
    pass
