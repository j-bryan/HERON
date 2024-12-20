
# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Holds the template information for creating LCOE SWEEP OPT input files.
"""
import dill as pk
from pathlib import Path

from .imports import Base
from .types import HeronCase, Component, Source
from .raven_template import RavenTemplate
from .bilevel_templates import BilevelTemplate
from .flat_templates import FlatMultiConfigTemplate
from .debug_template import DebugTemplate


class TemplateDriver(Base):
  # Map HERON features (determined by parts of case, components, and sources objects) to their FeatureDrivers.
  # Decide which template(s) to load.
  # Set naming conventions used throughout the templates
  def __init__(self):
    super().__init__()
    self.template = None  # type: RavenTemplate

  ##############
  # Public API #
  ##############
  def create_workflow(self, case: HeronCase, components: list[Component], sources: list[Source]) -> None:
    """
    Create a workflow for the specified Case and its components and sources
    @ In, case, HeronCase, the HERON case
    @ In, components, list[Component], components in HERON case
    @ In, sources, list[Source], external models, data, and functions
    @ Out, None
    """
    if case.debug["enabled"]:
      # Debug mode runs a workflow with fixed capacities with lots of outputs to help determine if a simulation has
      # been correctly specified.
      self.template = DebugTemplate()
    elif self._has_only_static_history(sources) \
         and self._number_of_static_history_samples(case, sources) == 1 \
         and not self._has_uncertain_econ_params(components) \
         and case.get_mode() == "sweep":
      # Fixed history workflow: only run the dispatch optimization once per capacity configuration.
      # This is quite a restrictive case due to some limitations in how sampling and post-processing is done in
      # RAVEN.
      self.template = FlatMultiConfigTemplate()
    elif self._has_all_capacities_fixed(components):
      # Fixed configuration workflow: analyze a fixed system configuration over many synthetic histories.
      # This is like a generalization of debug mode. All types of uncertain economic parameters can be accommodated
      # in this type of workflow.
      self.template = BilevelTemplate(case, sources)  # FIXME: using bilevel template until this can be implemented
      # TODO: FlatMultiDispatchTemplate
    else:
      # Use the bilevel problem formulation. Outer workflow samples component capacities and uncertain economic
      # parameters. Inner workflow performs dispatch optimization over multiple synthetic histories.
      # This catches a large number of cases that are not easily done in a flat workflow in RAVEN:
      #   - Multiple histories and capacity configurations (PostProcessor won't calculate statistics for each capacity)
      #   - Any opt mode case (can't specify both a sampler and an optimizer in a MultiRun step)
      #   -
      self.template = BilevelTemplate(case, sources)

    self.template.loadTemplate()
    self.template.createWorkflow(case, components, sources)

  def write_workflow(self, loc: str, case: HeronCase, components: list[Component], sources: list[Source]) -> None:
    print('========================')
    print('HERON: writing files ...')
    print('========================')
    self.template.writeWorkflow(loc, case, components, sources)

    # Write library of info so it can be read in dispatch during inner run. Doing this here ensures that the lib file
    # is written just once, no matter the number of workflow files written by the template.
    if isinstance(loc, str):
      loc = Path(loc)
    data = (case, components, sources)
    lib_name = self.template.namingTemplates["lib file"]
    lib_file = loc / lib_name
    with lib_file.open("wb") as lib:
      pk.dump(data, lib)
    print(f"Wrote '{lib_name}' to '{str(loc)}'")

  ###################
  # Utility methods #
  ###################
  @staticmethod
  def _has_all_capacities_fixed(components: list[Component]) -> bool:
    """
    Checks if all components have fixed capacities
    @ In, components, list[Component], list of HERON case components
    @ Out, has_all_capacities_fixed, bool, if all components have fixed capacities
    """
    return not any([comp.get_capacity(None, raw=True).is_parametric() for comp in components])

  @staticmethod
  def _has_only_static_history(sources: list[Source]) -> bool:
    """
    Checks if static history is being used and no synthetic history model is specified
    @ In, sources, list[Source], list of source placeholders
    @ Out, has_static_history, bool, if all components have fixed capacities
    """
    source_types = [source.type for source in sources]
    has_static_history = "CSV" in source_types
    has_synth_history = "ARMA" in source_types
    return has_static_history and not has_synth_history

  @staticmethod
  def _has_uncertain_econ_params(components: list[Component]) -> bool:
    """
    Checks if any components have uncertain cashflow parameters which affect the dispatch. For this to be the case,
    a component must be dispatchable and must have an hourly recurring cashflow with an uncertain parameter.
    @ In, components, list[Component], HERON case components
    @ Out, has_uncertain_variable_costs, bool, if there are any uncertain variable costs for dispatchable componentss
    """
    for component in components:
      if len(component.get_uncertain_cashflow_params()) > 0:
        return True
    return False

  @staticmethod
  def _number_of_static_history_samples(case: HeronCase, sources: list[Source]) -> int:
    """
    Gets the maximum number of static history samples among CSV sources
    @ In, case, HeronCase, the case object
    @ In, source, list[Source], file sources
    @ Out, num_samples, int, number of static history samples
    """
    return max(
      map(
        lambda x: x.get_structure(case)["num_samples"],
        filter(lambda x: x.type == "CSV", sources)
      ),
    )
