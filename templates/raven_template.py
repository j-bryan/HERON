# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  RAVEN workflow templates

  @author: j-bryan
  @date: 2024-10-29
"""
from pathlib import Path
import itertools as it
import xml.etree.ElementTree as ET

from .types import HeronCase, Component, Source, ValuedParam
from .naming_utils import get_result_stats, get_component_activity_vars, get_opt_objective, get_statistics, Statistic
from .xml_utils import add_node_to_tree, stringify_node_values
from .snippet_utils import load_pickled_rom, print_rom_meta

from .snippets.base import RavenSnippet
from .snippets.runinfo import RunInfo
from .snippets.steps import Step, MultiRun, IOStep
from .snippets.samplers import Sampler, SampledVariable, Grid, Stratified, CustomSampler, EnsembleForward
from .snippets.optimizers import BayesianOptimizer, GradientDescent
from .snippets.models import GaussianProcessRegressor, PickledROM, EnsembleModel, HeronDispatchModel
from .snippets.distributions import Distribution, Uniform
from .snippets.outstreams import PrintOutStream, OptPathPlot
from .snippets.dataobjects import DataObject, PointSet, DataSet
from .snippets.variablegroups import VariableGroup
from .snippets.files import File
from .snippets.factory import factory as snippet_factory

from .imports import xmlUtils, Template


# NOTE: Leave this here! Moving this to xml_utils.py will cause a circular import problem with snippets.factory.py
def parse_to_snippets(node: ET.Element) -> ET.Element:
  """
  Builds an XML tree that looks exactly like node but with RavenSnippet objects where defined.
  @ In, node, ET.Element, the node to parse
  @ Out, parsed: ET.Element, the parsed XML node
  """
  # Base case: The node matches a registered RavenSnippet class. RavenSnippets know how to represent
  # their entire contiguous block of XML, so no further recursion is necessary once a valid RavenSnippet
  # is found.
  if snippet_factory.is_registered(node):
    snippet = snippet_factory.from_xml(node)
    return snippet

  # If the node doesn't match a registered RavenSnippet class, copy over the node to the
  parsed = ET.Element(node.tag, node.attrib)
  parsed.text = node.text
  parsed.tail = node.tail

  # Recurse over node children (if any)
  for child in node:
    parsed_child = parse_to_snippets(child)
    parsed.append(parsed_child)

  return parsed

class RavenTemplate(Template):
  """ Template class for RAVEN workflows """
  # Default stats abbreviations. Different run modes have different defaults
  DEFAULT_STATS_NAMES = {
    "opt": ["expectedValue", "sigma", "median"],
    "sweep": ["maximum", "minimum", "percentile", "samples", "variance"]
  }

  # Prefixes for financial metrics only
  FINANCIAL_PREFIXES = ["sharpe", "sortino", "es", "VaR", "glr"]
  FINANCIAL_STATS_NAMES = ["sharpeRatio", "sortinoRatio", "expectedShortfall", "valueAtRisk", "gainLossRatio"]

  def __init__(self) -> None:
    super().__init__()
    # Naming templates
    self.addNamingTemplates({'jobname'        : '{case}_{io}',
                             'stepname'       : '{action}_{subject}',
                             'variable'       : '{unit}_{feature}',
                             'dispatch'       : 'Dispatch__{component}__{tracker}__{resource}',
                             'tot_activity'   : 'TotalActivity__{component}__{tracker}__{resource}',
                             'data object'    : '{source}_{contents}',
                             'distribution'   : '{variable}_dist',
                             'ARMA sampler'   : '{rom}_sampler',
                             'lib file'       : 'heron.lib', # TODO use case name?
                             'cashfname'      : '_{component}{cashname}',
                             're_cash'        : '_rec_{period}_{driverType}{driverName}',
                             'cluster_index'  : '_ROM_Cluster',
                             'metric_name'    : '{stats}_{econ}',
                             'statistic'      : '{prefix}_{name}'
                             })

  ########################
  # PUBLIC API FUNCTIONS #
  ########################

  def loadTemplate(self) -> None:
    """
    Load a template XML file into an ET.Element tree
    @ In, None,
    @ Out, None
    """
    this_file_dir = Path(__file__).parent
    template_path = this_file_dir / self.template_path
    raw_template, _ = xmlUtils.loadToTree(str(template_path))
    # Parsing the XML tree into RavenSnippet classes gives us access to handy attributes and methods for manipulating
    # the template XML.
    self._template = parse_to_snippets(raw_template)

  def createWorkflow(self, case: HeronCase, components: list[Component], sources: list[Source]) -> None:
    """
    Create a workflow for the specified Case and its components and sources
    @ In, case, HeronCase, the HERON case
    @ In, components, list[Component], components in HERON case
    @ In, sources, list[Source], external models, data, and functions
    @ Out, None
    """
    # Universal workflow settings
    self._set_verbosity(case.get_verbosity())
    self._initialize_runinfo(case)

  def writeWorkflow(self,
                    destination: str,
                    case: HeronCase,
                    components: list[Component],
                    sources: list[Source],
                    run: bool = False) -> None:
    """
    Write RAVEN workflow
    @ In, destination, str, path to write workflows to
    @ In, case, HeronCase, the HERON case
    @ In, components, list[Component], components in HERON case
    @ In, sources, list[Source], external models, data, and functions
    @ In, run, bool, if True then attempt to run the workflows
    @ Out, None
    """
    # Ensure all node attribute values and text are expressed as strings. Errors are thrown if any of these aren't
    # strings. Enforcing this here allows flexibility with how node values are stored and manipulated before write
    # time, such as storing values as lists or numeric types. For example, text fields which are a comma-separated
    # list of values can be stored in the RavenSnippet object as a list, and new items can be inserted into that
    # list as needed, then the list can be converted to a string only now at write time.
    stringify_node_values(self._template)

    # Remove any unused top-level nodes (Models, Samplers, etc.) to keep things looking clean
    for node in self._template:
      if len(node) == 0:
        self._template.remove(node)

    dest_dir = Path(destination)
    xml_file = dest_dir / self.write_name

    xml_file.write_text(xmlUtils.prettify(self._template))
    print(f"Wrote '{self.write_name}' to '{str(dest_dir)}'")

    # run, if requested
    if run:
      self.runWorkflow(destination)

  #############################################
  # UTILITIES FOR ADDING SNIPPETS TO TEMPLATE #
  #############################################
  def _add_snippet(self, snippet: RavenSnippet, parent: str | ET.Element | None = None) -> None:
    """
    Add an XML snippet to the template XML
    @ In, snippet, RavenSnippet, the XML snippet to add
    @ In, parent, str | ET.Element | None, the parent node to add the snippet
    """
    if isinstance(snippet, ET.Element) and not isinstance(snippet, RavenSnippet):
      raise TypeError(f"The XML block to be added is not a RavenSnippet object. Received type: {type(snippet)}. "
                      "Perhaps something went wrong when parsing the template XML, and the correct RavenSnippet "
                      "suclass wasn't found?")
    if snippet is None:
      raise ValueError("Received None instead of a RavenSnippet object. Perhaps something went wrong when finding "
                       "an XML node?")

    # If a parent node was provided, just append the snippet to its parent node.
    if isinstance(parent, ET.Element):
      parent.append(snippet)
      return

    # Otherwise, figure out where to put the XML snippet. Either a string for a parent node (maybe doesn't exist yet)
    # was provided, or the desired location is inferredfrom .he snippet "snippet_class" (e.g. Models, DataObjects, etc.).
    if parent and isinstance(parent, str):
      parent_path = parent
    else:
      # Find parent node based on snippet "class" attribute
      parent_path = snippet.snippet_class

    if parent_path is None:
      raise ValueError(f"The path to a parent node for node {snippet} could not be determined!")

    # Make the parent node if it doesn't exist. This is helpful if it's unknown if top-level nodes (Models, Optimizers,
    # Steps, etc.) exist without having to add a check everywhere a snippet needs to get added.
    add_node_to_tree(snippet, parent_path, self._template)

  ####################
  # MAJOR CASE MODES #
  ####################
  # These functions help to define and connect features of the RAVEN workflow for "sweep" and "opt" modes. These use
  # a few abstract methods which should be implemented by subclasses to correctly handle each mode.

  def _sweep_case(self, case: HeronCase, components: list[Component]) -> tuple[Grid, PointSet, PrintOutStream]:
    """
    Sets up everything necessary for running a sweep with "model" and outputting the results.
    @ In, inputs, list[RavenSnippet], list of inputs to add as Input nodes in the optimization MultiRun step
    @ In, model, Model, model to be optimized
    @ In, case, Case, HERON case object
    @ In, components, list[Component], HERON component objects
    @ In, sources, list[Source], Source objects for data sources
    """
    # Fetch some helpful variable groups
    capacities_vargroup = self._template.find("VariableGroups/Group[@name='GRO_capacities']")
    results_vargroup = self._template.find("VariableGroups/Group[@name='GRO_outer_results']")

    # Define the grid sampler and its accompanying results PointSet
    sampler, results_data = self._create_grid_sampler(case, components, capacities_vargroup, results_vargroup)

    # Print the results of the sweep
    print_results = PrintOutStream("sweep")
    print_results.source = results_data
    self._add_snippet(print_results)

    return sampler, results_data, print_results

  def _sweep_case(self,
                  inputs: list[RavenSnippet],
                  model: RavenSnippet,
                  case: HeronCase,
                  components: list[Component]) -> None:
    sampler, results_data = self._create_sweep_sampler(case, components)
    # Print the results of the sweep
    print_results = PrintOutStream("sweep")
    print_results.source = results_data
    self._add_snippet(print_results)

    # Use a MultiRun to run to the model over the grid points
    multirun = MultiRun("sweep")
    for inp in inputs:
      multirun.add_input(inp)
    multirun.add_model(model)
    multirun.add_sampler(sampler)
    multirun.add_output(results_data)
    multirun.add_output(print_results)
    self._add_snippet(multirun)

  def _opt_case(self,
                inputs: list[RavenSnippet],
                model: RavenSnippet,
                case: HeronCase,
                components: list[Component],
                sources: list[Source],
                capacities: VariableGroup,
                results: VariableGroup):
    """
    Sets up everything necessary for running an optimizer with "model" and outputting the results.
    @ In, inputs, list[RavenSnippet], list of inputs to add as Input nodes in the optimization MultiRun step
    @ In, model, Model, model to be optimized
    @ In, case, Case, HERON case object
    @ In, components, list[Component], HERON component objects
    @ In, sources, list[Source], Source objects for data sources
    """
    # Define XML blocks for optimization: optimizer, sampler, ROM, etc.
    opt_strategy = case.get_opt_strategy()
    if opt_strategy == "BayesianOpt":
      optimizer = self._create_bayesian_opt(case, components)
    elif opt_strategy == "GradientDescent":
      optimizer = self._create_gradient_descent(case, components)
    else:
      raise ValueError(f"Template does not recognize optimization strategy {opt_strategy}.")

    # Set optimizer <TargetEvaluation> data object
    results_data = PointSet("opt_eval")
    results_data.inputs.append(capacities)
    results_data.outputs.append(results)
    self._add_snippet(results_data)
    optimizer.target_evaluation = results_data

    # Set optimizer objective function
    objective = get_opt_objective(case)
    optimizer.objective = objective
    if objective not in results.variables:
      results.variables.insert(0, objective)

    # Add case labels to the optimizer
    self._add_labels_to_sampler(optimizer, case.get_labels())

    # Create a data object for saving the optimization path
    solution_export = PointSet("opt_soln")
    solution_export.inputs.append("trajID")
    solution_export.outputs.extend(["iteration", "accepted", capacities, results])
    self._add_snippet(solution_export)

    # Create a MultiRun step to run the optimization
    multirun = MultiRun("optimize")
    for inp in inputs:
      multirun.add_input(inp)
    multirun.add_model(model)
    multirun.add_optimizer(optimizer)
    multirun.add_solution_export(solution_export)
    multirun.add_output(results_data)
    self._add_snippet(multirun)

    # Plot the result of the optimization
    opt_path_plot = OptPathPlot("opt_path")
    opt_path_plot.source = solution_export
    opt_path_plot.variables = ["GRO_capacities", objective]
    self._add_snippet(opt_path_plot)

    # Print the results of the optimization
    print_results = PrintOutStream("opt_soln")
    print_results.source = solution_export
    print_results.add_subelements(clusterLabel="trajID")
    self._add_snippet(print_results)

    plot_step = IOStep(f"plot")
    plot_step.add_input(solution_export)
    plot_step.add_output(opt_path_plot)
    plot_step.add_output(print_results)
    self._add_snippet(plot_step)

    # Add steps to the Sequence in RunInfo
    self._add_step_to_sequence(multirun)
    self._add_step_to_sequence(plot_step)

  ##############################
  # FEATURE BUILDING UTILITIES #
  ##############################
  # These functions help set options and build workflow features. They are roughly organized by which portion of the
  # RAVEN template they modify.

  # Global attributes
  def _set_verbosity(self, verbosity: str) -> None:
    """
    Sets the verbosity attribute of the root Simulation node
    @ In, verbosity, str, the verbosity level
    @ Out, None
    """
    self._template.set("verbosity", verbosity)

  # RunInfo
  def _initialize_runinfo(self, case: HeronCase, case_name: str = "") -> RunInfo:
    """
    Initializes the RunInfo node of the workflow
    @ In, case, Case, the HERON Case object
    @ In, case_name, str, optional, the case name
    @ Out, run_info, RunInfo, a RunInfo object describing case run info
    """
    run_info = self._template.find("RunInfo")  # type: RunInfo

    if case_name:
      run_info.job_name = case_name
      run_info.working_dir = case_name

    return run_info

  def _add_step_to_sequence(self, step: Step, index: int | None = None) -> None:
    run_info = self._template.find("RunInfo")  # type: RunInfo
    idx = index if index is not None else len(run_info.sequence)
    run_info.sequence.insert(idx, step)

  def _update_batch_size(self, case: HeronCase) -> None:
    if case.get_mode() == "sweep":
      sampler = self._template.find("Samplers/Grid")
    elif case.get_opt_strategy() == "BayesianOpt":
      sampler = self._template.find("Optimizers/BayesianOptimizer")
    elif case.get_opt_strategy() == "GradientDescent":
      sampler = self._template.find("Optimizers/GradientDescent")
    else:
      raise ValueError("Sampler not found")

    run_info = self._template.find("RunInfo")
    case.outerParallel = sampler.num_sampled_vars + 1
    run_info.batch_size = case.outerParallel
    run_info.internal_parallel = True

  # Steps
  def _load_file_to_object(self, source: Source, target: RavenSnippet) -> IOStep:
    # Get the file to load. Might already exist in the template XML
    file = self._template.find("Files/Input[@name='{source.name}']")  # type: File
    if file is None:
      file = File(source.name)
      file.path = source._target_file

    # Create an IOStep to load the file to the target
    step_name = self.namingTemplates["stepname"].format(action="read", subject=source.name)
    step = IOStep(step_name)
    step.append(file.to_assembler_node("Input"))
    step.append(target.to_assembler_node("Output"))

    self._add_snippet(file)
    self._add_snippet(step)

    return step

  def _print_metadata(self, target: RavenSnippet, step_name: str | None = None) -> IOStep:
    """
    Create an IOStep to print the metadata for a ROM. Makes and adds the requisite DataSet and OutStream nodes.
    @ In, target, RavenSnippet, target entity
    @ Out, step, IOStep, the IOStep
    """
    # Create the output data object
    dataset_name = f"{target.name}_meta"
    dataset = DataSet(dataset_name)
    self._add_snippet(dataset)

    # Create the outstream for the dataset
    outstream = PrintOutStream(dataset_name)
    outstream.source = dataset
    self._add_snippet(outstream)

    # create step
    step_name = step_name or self.namingTemplates["stepname"].format(action="print", subject=dataobject.name)
    step = self._template.find(f"Steps/IOStep[@name='{step_name}']") or IOStep(step_name)
    step.add_input(target)
    step.add_output(dataset)
    step.add_output(outstream)
    self._add_snippet(step)

    return step

  def _print_dataobject(self, dataobject: DataObject, step_name: str | None = None) -> IOStep:
    # Create the outstream for the dataset
    outstream = PrintOutStream(dataobject.name)
    outstream.source = dataobject
    self._add_snippet(outstream)

    # create step
    step_name = step_name or self.namingTemplates["stepname"].format(action="print", subject=dataobject.name)
    step = self._template.find(f"Steps/IOStep[@name='{step_name}']") or IOStep(step_name)
    step.add_input(dataobject)
    step.add_output(outstream)
    self._add_snippet(step)

    return step

  # VariableGroups
  def _create_case_labels_vargroup(self, labels: dict[str, str], name: str = "GRO_case_labels") -> VariableGroup:
    group = VariableGroup(name)
    group.variables.extend(map(lambda label: f"{label}_label", labels.keys()))
    return group

  def _get_statistical_results_vars(self, case: HeronCase, components: list[Component]) -> list[str]:
    """
    Collects result metric names for statistical metrics
    @ In, case, Case, HERON case
    @ In, components, list[Component], HERON components
    @ Out, var_names, list[str], list of variable names
    """
    # Add statistics for economic metrics to variable group. Use all statistics.
    default_names = self.DEFAULT_STATS_NAMES.get(case.get_mode(), [])
    # This gets the unique valuesfrom .efault_names and the case result statistics dict keys. Set operations
    # look cleaner but result in a randomly ordered list. Having a consistent ordering of statistics is beneficial
    #from . UX standpoint.
    stats_names = list(dict.fromkeys(default_names + list(case.get_result_statistics())))
    econ_metrics = case.get_econ_metrics(nametype="output")
    stats_var_names = get_result_stats(econ_metrics, stats_names, case)

    # Add total activity statistics for variable group. Use only non-financial statistics.
    non_fin_stat_names = [name for name in stats_names if name not in self.FINANCIAL_STATS_NAMES]
    tot_activity_metrics = get_component_activity_vars(components, self.namingTemplates["tot_activity"])
    activity_var_names = get_result_stats(tot_activity_metrics, non_fin_stat_names, case)

    var_names = stats_var_names + activity_var_names

    # The optimization objective might not have made it into the list. Make sure it's there.
    if case.get_mode() == "opt" and (objective := get_opt_objective(case)) not in var_names:
      var_names.insert(0, objective)

    return var_names

  def _get_deterministic_results_vars(self, case: HeronCase, components: list[Component]) -> list[str]:
    """
    Collects result metric names for deterministic cases
    @ In, case, Case, HERON case
    @ In, components, list[Component], HERON components
    @ Out, var_names, list[str], list of variable names
    """
    econ_metrics = case.get_econ_metrics(nametype="output")
    tot_activity_metrics = get_component_activity_vars(components, self.namingTemplates["tot_activity"])
    var_names = econ_metrics + tot_activity_metrics
    return var_names

  def _get_activity_metrics(self, components: list[Component]):
    """
    Gets the names of component activity metrics
    @ In, components, list[Component], HERON components
    @ Out, act_metrics, list[str], component activity metric names
    """
    act_metrics = []
    for component in components:
      for tracker in component.get_tracking_vars():
        resource_list = sorted(list(component.get_resources()))
        for resource in resource_list:
          # NOTE: Assumes the only activity metric we care about is total activity
          default_stats_tot_activity = self.namingTemplates["tot_activity"].format(component=component.name, tracker=tracker, resource=resource)
          act_metrics.append(default_stats_tot_activity)
    return act_metrics

  # Models
  def _pickled_rom_from_source(self, source: Source) -> PickledROM:
    rom = PickledROM(source.name)
    if source.needs_multiyear is not None:
      rom.add_subelements({"Multicycle" : {"cycles": source.needs_multiyear}})
    if source.limit_interp is not None:
      rom.add_subelements(maxCycles=source.limit_interp)
    self._add_snippet(rom)
    if source.eval_mode == 'clustered':
      ET.SubElement(rom, "clusterEvalMode").text = "clustered"
    return rom

  def _add_time_series_roms(self, ensemble_model: EnsembleModel, case: HeronCase, sources: list[Source]):
    """
    Create and modify snippets based on sources
    @ In, case, Case, HERON case
    @ In, sources, list[Source], case sources
    @ Out, None
    """
    dispatch_eval = self._template.find("DataObjects/DataSet[@name='dispatch_eval']")  # type: DataSet

    # Gather any ARMA sourcesfrom .he list of sources
    arma_sources = [s for s in sources if s.is_type("ARMA")]

    # Add cluster index info to dispatch variable groups and data objects
    if any(source.eval_mode == "clustered" for source in arma_sources):
      vg_dispatch = self._template.find("VariableGroups/Group[@name='GRO_dispatch']")  # type: VariableGroup
      vg_dispatch.variables.append(self.namingTemplates["cluster_index"])
      dispatch_eval.add_index(self.namingTemplates["cluster_index"], "GRO_dispatch_in_Time")

    # Add models, steps, and their requisite data objects and outstreams for each case source
    for source in arma_sources:
      # An ARMA source is a pickled ROM that needs to be loaded.
      # Load the ROMfrom .ile
      source_file, pickled_rom, load_iostep = load_pickled_rom(source)
      self._add_snippet(source_file)
      self._add_snippet(pickled_rom)
      self._add_snippet(load_iostep)
      self._add_step_to_sequence(load_iostep, index=0)

      # Print the pickled ROM metadata
      meta_dataset, meta_outstream, meta_iostep = print_rom_meta(pickled_rom)
      self._add_snippet(meta_dataset)
      self._add_snippet(meta_outstream)
      self._add_snippet(meta_iostep)
      self._add_step_to_sequence(meta_iostep, index=1)

      # Add loaded ROM to the EnsembleModel
      inp_name = self.namingTemplates["data object"].format(source=source.name, contents="placeholder")
      inp_do = PointSet(inp_name)
      inp_do.inputs.append("scaling")
      self._add_snippet(inp_do)

      eval_name = self.namingTemplates["data object"].format(source=source.name, contents="samples")
      eval_do = DataSet(eval_name)
      eval_do.inputs.append("scaling")
      out_vars = source.get_variable()
      eval_do.outputs.extend(out_vars)
      eval_do.add_index(case.get_time_name(), out_vars)
      eval_do.add_index(case.get_year_name(), out_vars)
      if source.eval_mode == "clustered":
        eval_do.add_index(self.namingTemplates["cluster_index"], out_vars)
      self._add_snippet(eval_do)

      rom_assemb = pickled_rom.to_assembler_node("Model")
      rom_assemb.append(inp_do.to_assembler_node("Input"))
      rom_assemb.append(eval_do.to_assembler_node("TargetEvaluation"))
      ensemble_model.append(rom_assemb)

      # update variable group with ROM output variable names
      self._template.find("VariableGroups/Group[@name='GRO_dispatch_in_Time']").variables.extend(out_vars)

  def _get_stats_for_econ_postprocessor(self, case: HeronCase, econ_vars: list[str], activity_vars: list[str]) -> list[tuple[Statistic, str]]:
    # Econ metrics with all statistics names
    # NOTE: This logic is borrowedfrom .avenTemplate._get_statistical_results_vars, but it's more useful to have the names,
    # prefixes, and variable name separate here, not as one big string. Otherwise, we have to try to break that string
    # back up, which would be sensitive to metric and variable naming conventions. We duplicate a little of the logic but
    # get something more robust in return.
    default_names = self.DEFAULT_STATS_NAMES.get(case.get_mode(), [])
    stats_names = list(dict.fromkeys(default_names + list(case.get_result_statistics())))
    econ_stats = get_statistics(stats_names, case.stats_metrics_meta)
    # Activity metrics with non-financial statistics
    non_fin_stat_names = [name for name in stats_names if name not in self.FINANCIAL_STATS_NAMES]
    activity_stats = get_statistics(non_fin_stat_names, case.stats_metrics_meta)

    # Collect the statistics to add to the postprocessor
    stats_to_add = list(it.chain(
      it.product(econ_stats, econ_vars),
      it.product(activity_stats, activity_vars)
    ))

    # The metric needed for the objective function might not have been added yet.
    if case.get_mode() == "opt":
      opt_settings = case.get_optimization_settings()
      try:
        statistic = opt_settings["stats_metric"]["name"]
      except (KeyError, TypeError):
        statistic = "expectedValue"  # default to expectedValue
      opt_stat, = get_statistics([statistic], case.stats_metrics_meta)
      target_var, _ = case.get_opt_metric()
      target_var_output_name = case.economic_metrics_meta[target_var]["output_name"]
      if (opt_stat, target_var_output_name) not in stats_to_add:
        stats_to_add.append((opt_stat, target_var_output_name))

    return stats_to_add

  # Distributions and SampledVariables
  def _create_new_sampled_capacity(self, var_name: str, capacities: list[float]):
    """
    Creates a uniform distribution and SampledVariable object for a given list of capacities
    @ In, var_name, str, name of the variable
    @ In, capacities, list[float], list of capacity values
    @ Out, sampled_var, SampledVariable, variable to be sampled
    """
    dist_name = self.namingTemplates["distribution"].format(variable=var_name)
    dist = Uniform(dist_name)
    min_cap = min(capacities)
    max_cap = max(capacities)
    dist.lower_bound = min_cap
    dist.upper_bound = max_cap
    self._add_snippet(dist)

    sampled_var = SampledVariable(var_name)
    sampled_var.distribution = dist

    return sampled_var

  def _get_uncertain_cashflow_params(self, components: list[Component]) -> tuple[list[SampledVariable], list[Distribution]]:
    """
    Create SampledVariable and Distribution snippets for all uncertain cashflow parameters.
    @ In, components, list[Component]
    @ Out, sampled_vars, list[SampledVariable], objects to link sampler variables to distributions
    @ Out, distributions, list[Distribution], distribution snippets
    """
    sampled_vars = []
    distributions = []

    # For each component, cashflow, and cashflow equation parameter, find any which are uncertain, and create distribution
    # and sampled variable objects.
    for component in components:
      for cashflow in component.get_cashflows():
        for param_name, vp in cashflow.get_uncertain_params().items():
          unit_name = f"{component.name}_{cashflow.name}"
          feat_name = self.namingTemplates["variable"].format(unit=unit_name, feature=param_name)
          dist_name = self.namingTemplates["distribution"].format(variable=feat_name)

          # Reconstruct distribution XML nodefrom .aluedParam definition
          dist_node = vp._vp.get_distribution()  # type: ET.Element
          dist_node.set("name", dist_name)
          dist_snippet = snippet_factory.from_xml(dist_node)
          distributions.append(dist_snippet)

          # Create sampled variable snippet
          sampler_var = SampledVariable(feat_name)
          sampler_var.distribution = dist_snippet
          sampled_vars.append(sampler_var)

    return sampled_vars, distributions

  # Samplers
  def _create_sampler_variables(self, case: HeronCase, components: list[Component]) -> tuple[dict[SampledVariable, list[float]], dict[str, ValuedParam]]:
    """
    Create the Distribution and SampledVariable objects and the list of constant capacities that need to
    be added to samplers and optimizers.
    @ In, case, Case, HERON case
    @ In, components, list[Component], HERON components
    @ Out, sampled_variables, dict[SampledVariable, list[float]], variable objects for the sampler/optimizer
    @ Out, constants, dict[str, float], constant variables
    """
    sampled_variables = {}
    constants = {}

    # Make Distribution and SampledVariable objects for sampling dispatch variables
    for key, value in case.dispatch_vars.items():
      var_name = self.namingTemplates["variable"].format(unit=key, feature="dispatch")
      vals = value.get_value(debug=case.debug["enabled"])
      if isinstance(vals, list):
        sampled_var = self._create_new_sampled_capacity(var_name, vals)
        sampled_variables[sampled_var] = vals

    # Make Distribution and SampledVariable objects for capacity variables. Capacities with non-parametric
    # ValuedParams are fixed values and are added instead as constants.
    for component in components:
      interaction = component.get_interaction()
      name = component.name
      var_name = self.namingTemplates["variable"].format(unit=name, feature="capacity")
      cap = interaction.get_capacity(None, raw=True)  # type: ValuedParam

      if not cap.is_parametric():  # we already know the value
        continue

      vals = cap.get_value(debug=case.debug["enabled"])
      if isinstance(vals, list):  # multiple values meaning either opt bounds or sweep values
        sampled_var = self._create_new_sampled_capacity(var_name, vals)
        sampled_variables[sampled_var] = vals
      else:  # just one value meaning it's a constant
        constants[var_name] = vals

    return sampled_variables, constants

  def _add_labels_to_sampler(self, sampler: Sampler, labels: dict[str, str]) -> None:
    """
    Add case labels as constants for a sampler or optimizer
    @ In, sampler, Sampler, sampler to add labels to
    @ In, case, Case, HERON case
    @ Out, None
    """
    for key, value in labels.items():
      var_name = self.namingTemplates["variable"].format(unit=key, feature="label")
      sampler.add_constant(var_name, value)

  def _configure_static_history_sampler(self,
                                        custom_sampler: CustomSampler,
                                        case: HeronCase,
                                        sources: list[Source],
                                        scaling: int | None = 1.0) -> None:
    indices = [case.get_year_name(), case.get_time_name()]
    cluster_index = self.namingTemplates["cluster_index"]
    if case.debug["enabled"]:
      indices.append(cluster_index)

    time_series_vargroup = self._template.find("VariableGroups/Group[@name='GRO_timeseries']")  # type: VariableGroup

    for source in filter(lambda x: x.is_type("CSV"), sources):
      # Add the source variables to the GRO_timeseries_in variable group
      source_vars = source.get_variable()
      self._template.find("VariableGroups/Group[@name='GRO_timeseries']").variables.extend(source_vars)

      # Create a new <DataObject> that will store the csv data
      csv_dataset = DataSet(source.name)
      csv_dataset.inputs.extend([case.get_time_name(), case.get_year_name()])
      csv_dataset.outputs.extend(source_vars)
      for index in indices:
        csv_dataset.add_index(index, source_vars)
      self._add_snippet(csv_dataset)

      # Use an IOStep to load the CSV data into the DataSet
      read_static = self._load_file_to_object(source, csv_dataset)
      self._add_step_to_sequence(read_static, index=0)

      # Add variables to the custom sampler for the
      custom_sampler.append(csv_dataset.to_assembler_node("Source"))
      for var in it.filterfalse(custom_sampler.has_variable, it.chain(indices, source_vars)):
        # NOTE: Being careful not to add duplicate time index variables to the custom sampler in case somebody tries
        # to include multiple CSV sources.
        custom_sampler.add_variable(SampledVariable(var))

      # Add the static history variables to the dispatch model
      new_vars = it.chain(
        source_vars,
        filter(lambda x: x not in time_series_vargroup.variables, indices)
      )
      time_series_vargroup.variables.extend(new_vars)

    if custom_sampler.find("constant[@name='scaling']") is None and scaling is not None:
      custom_sampler.add_constant("scaling", scaling)

  def _create_grid_sampler(self,
                           case: HeronCase,
                           components: list[Component],
                           capacity_vars: VariableGroup | str | list[str],
                           results_vars:VariableGroup | str | list[str]) -> tuple[Grid, PointSet]:
    # Define a PointSet for the results variables at each grid point
    results_data = PointSet("grid")

    if isinstance(capacity_vars, list):
      results_data.inputs.extend(capacity_vars)
    else:
      results_data.inputs.append(capacity_vars)

    if isinstance(results_vars, list):
      results_data.outputs.extend(results_vars)
    else:
      results_data.outputs.append(results_vars)

    self._add_snippet(results_data)

    # Define grid sampler and build the variables and their distributions that it'll sample
    sampler = Grid("grid")
    vars, consts = self._create_sampler_variables(case, components)
    for sampled_var, vals in vars.items():
      sampler.add_variable(sampled_var)
      sampled_var.use_grid(construction="custom", type="value", values=sorted(vals))
    for var_name, val in consts.items():
      sampler.add_constant(var_name, val)

    # Number of "denoises" for the sampler is the number of samples it should take
    sampler.denoises = case.get_num_samples()

    # If there are any case labels, make a variable group for those and add it to the "grid" PointSet.
    # These labels also need to get added to the sampler as constants.
    labels = case.get_labels()
    if labels:
      vargroup = self._create_case_labels_vargroup(labels)
      self._add_snippet(vargroup)
      results_data.outputs.append(vargroup.name)
    self._add_labels_to_sampler(sampler, labels)

    return sampler, results_data

  def _create_ensemble_forward_sampler(self, samplers: list[Sampler], name: str = "ensemble_sampler") -> EnsembleForward:
      ensemble_sampler = EnsembleForward(name)
      for sampler in samplers:
        ensemble_sampler.append(sampler)
      return ensemble_sampler

  def _create_sweep_sampler(self, case: HeronCase, components: list[Component]):
    """
    Sets up the sampling strategy (with requisite data objects) for a sweep mode run
    """
    # Implement this in subclasses to define how the sampler(s) should be set up
    raise NotImplementedError

  # Optimizers
  def _create_bayesian_opt(self, case: HeronCase, components: list[Component]) -> BayesianOptimizer:
    """
    Set up the Bayesian optimization optimizer, LHS sampler, GPR model, and necessary distributions and data objects
    for using Bayesian optimization.
    """
    # Create major XML blocks
    optimizer = BayesianOptimizer("cap_opt")
    sampler = Stratified("LHS_samp")
    gpr = GaussianProcessRegressor("gpROM")

    # Add blocks to XML template
    self._add_snippet(optimizer)
    self._add_snippet(sampler)
    self._add_snippet(gpr)

    # Connect optimizer to sampler and ROM components
    optimizer.set_sampler(sampler)
    optimizer.set_rom(gpr)

    # Apply any specified optimization settings
    opt_settings = case.get_optimization_settings() or {}  # default to empty dict if None
    optimizer.set_opt_settings(opt_settings)
    # Set GPR kernel if provided
    if opt_settings and (custom_kernel := opt_settings["algorithm"]["BayesianOpt"].get("kernel", None)):
      gpr.custom_kernel = custom_kernel

    # Create sampler variables and their respective distributions
    vars, consts = self._create_sampler_variables(case, components)
    for sampled_var, vals in vars.items():
      sampled_var.use_grid(construction="equal", type="CDF", steps=4, values=[0, 1])
      optimizer.add_variable(sampled_var)
      sampler.add_variable(sampled_var)
    for var_name, val in consts.items():
      optimizer.add_constant(var_name, val)

    # Set number of denoises
    optimizer.denoises = case.get_num_samples()

    # Set GPR features list and target
    for component in components:
      name = component.name
      interaction = component.get_interaction()
      cap = interaction.get_capacity(None, raw=True)
      if cap.is_parametric() and isinstance(cap.get_value(debug=case.debug['enabled']) , list):
        gpr.features.append(self.namingTemplates["variable"].format(unit=name, feature="capacity"))
    gpr.target = get_opt_objective(case)

    return optimizer

  def _create_gradient_descent(self, case, components) -> GradientDescent:
    # Create necessary XML blocks
    optimizer = GradientDescent("cap_opt")
    self._add_snippet(optimizer)

    # Apply any specified optimization settings
    opt_settings = case.get_optimization_settings()
    optimizer.set_opt_settings(opt_settings)
    optimizer.objective = get_opt_objective(case)

    # Set number of denoises
    optimizer.denoises = case.get_num_samples()

    # Create sampler variables and their respective distributions
    vars, consts = self._create_sampler_variables(case, components)

    for sampled_var, vals in vars.items():
      # initial value
      min_val = min(vals)
      max_val = max(vals)
      delta = max_val - min_val
      # start 5% awayfrom .ero
      initial = min_val + 0.05 * delta if max_val > 0 else max_val - 0.05 * delta
      sampled_var.initial = initial
      optimizer.add_variable(sampled_var)

    for var_name, val in consts.items():
      optimizer.add_constant(var_name, val)

    return optimizer

  # Files
  def _get_function_files(self, sources: list[Source]) -> list[File]:
    """
    Get the File object for each source that is a Function
    @ In, sources, list[Source], the sources
    @ Out, files, list[File], the files
    """
    # Add Function sources as Files
    files = []
    for function in [s for s in sources if s.is_type("Function")]:
      file = self._template.find(f"Files/Input[@name='{function.name}']")
      if file is None:  # Add function to <Files> if not found there
        file = File(function.name)
        file.path = str(".." / Path(function._source))
        self._add_snippet(file)
      files.append(file)
    return files
