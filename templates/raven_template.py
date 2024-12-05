# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  RAVEN workflow templates

  @author: j-bryan
  @date: 2024-10-29
"""
import sys
import os
import itertools
import dill as pk
import xml.etree.ElementTree as ET

from .snippets.factory import factory as snippet_factory
from .snippets.base import RavenSnippet
from .snippets.runinfo import RunInfo
from .snippets.steps import Step, MultiRun, IOStep, PostProcess
from .snippets.samplers import Sampler, SampledVariable, Grid, Stratified, MonteCarlo, CustomSampler
from .snippets.optimizers import Optimizer, BayesianOptimizer, GradientDescent
from .snippets.models import Model, RavenCode, GaussianProcessRegressor, PickledROM, EconomicRatioPostProcessor
from .snippets.distributions import Distribution, Uniform
from .snippets.outstreams import OutStream, PrintOutStream, OptPathPlot
from .snippets.dataobjects import DataObject, PointSet, DataSet
from .snippets.variablegroups import VariableGroup
from .snippets.files import File

from .utils import get_component_activity_vars, add_node_to_tree, find_node, stringify_node_values

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
from HERON.src.Cases import Case
from HERON.src.Components import Component
from HERON.src.Placeholders import Placeholder
sys.path.pop()

RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))

sys.path.append(os.path.join(RAVEN_LOC, '..'))
from ravenframework.utils import xmlUtils
from ravenframework.InputTemplates.TemplateBaseClass import Template
sys.path.pop()



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
  # parsed.tail = node.tail

  # Recurse over node children (if any)
  for child in node:
    parsed_child = parse_to_snippets(child)
    parsed.append(parsed_child)

  return parsed


class RavenTemplate(Template):
  """ Template class for RAVEN workflows """

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

  # Default stats abbreviations. Different run modes have different defaults
  DEFAULT_STATS_NAMES = {
    "opt": ["expectedValue", "sigma", "median"],
    "sweep": ["maximum", "minimum", "percentile", "samples", "variance"]
  }

  # Prefixes for financial metrics only
  FINANCIAL_PREFIXES = ["sharpe", "sortino", "es", "VaR", "glr"]
  FINANCIAL_STATS_NAMES = ["sharpeRatio", "sortinoRatio", "expectedShortfall", "valueAtRisk", "gainLossRatio"]

  ########################
  # PUBLIC API FUNCTIONS #
  ########################

  def loadTemplate(self) -> None:
    this_file_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(this_file_dir, self.template_path)
    raw_template, _ = xmlUtils.loadToTree(template_path)
    # Parsing the XML tree into RavenSnippet classes gives us access to handy attributes and methods for manipulating
    # the template XML.
    self._template = parse_to_snippets(raw_template)

  def createWorkflow(self, case, components, sources) -> None:
    # Universal workflow settings
    self._set_verbosity(case.get_verbosity())
    self._initialize_runinfo(case)

  def writeWorkflow(self, destination, case, components, sources, run=False) -> None:
    """
      Write RAVEN workflow
      @ In, destination, str, path to write workflows to
      @ In, run, bool, if True then attempt to run the workflows
      @ Out, None
    """
    # Ensure all node attribute values and text are expressed as strings. Errors are thrown if any of these aren't
    # strings. Enforcing this here allows flexibility with how node values are stored and manipulated before write
    # time, such as storing values as lists or numeric types. For example, text fields which are a comma-separated
    # list of values can be stored in the RavenSnippet object as a list, and new items can be inserted into that
    # list as needed, then the list can be converted to a string only now at write time.
    stringify_node_values(self._template)

    file_name = os.path.abspath(os.path.join(destination, self.write_name))

    msg_format = 'Wrote "{1}" to "{0}/"'
    with open(file_name, 'w') as f:
      f.write(xmlUtils.prettify(self._template))
    print(msg_format.format(*os.path.split(file_name)))

    # write library of info so it can be read in dispatch during inner run
    # FIXME: This is written twice for bilevel workflows (not time consuming but unnecessary)
    data = (case, components, sources)
    lib_file = os.path.abspath(os.path.join(destination, self.namingTemplates['lib file']))
    with open(lib_file, 'wb') as lib:
      pk.dump(data, lib)
    print(msg_format.format(*os.path.split(lib_file)))

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
    # if not isinstance(snippet, RavenSnippet):
    #   raise TypeError(f"The XML block to be added is not a RavenSnippet object. Received type: {type(snippet)}. "
    #                   "")
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
    # was provided, or the desired location is inferred from the snippet "snippet_class" (e.g. Models, DataObjects, etc.).
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
  # These functions help to define and connect features of the RAVEN workflow for "sweep" and "opt" modes. These are
  # broadly applicable across bilevel and flat workflows.

  def _sweep_case(self, inputs: list[RavenSnippet], model: Model, case: Case, components: list[Component], sources: list[Placeholder]) -> MultiRun:
    """
    Sets up everything necessary for running a sweep with "model" and outputting the results.
    @ In, inputs, list[RavenSnippet], list of inputs to add as Input nodes in the optimization MultiRun step
    @ In, model, Model, model to be optimized
    @ In, case, Case, HERON case object
    @ In, components, list[Component], HERON component objects
    @ In, sources, list[Placeholder], placeholder objects for data sources
    """
    # Fetch some helpful variable groups
    capacities_vargroup = self._template.find("VariableGroups/Group[@name='GRO_capacities']")
    results_vargroup = self._template.find("VariableGroups/Group[@name='GRO_outer_results']")

    results_data = PointSet("grid")
    results_data.add_inputs(capacities_vargroup)
    results_data.add_outputs(results_vargroup)
    self._add_snippet(results_data)

    # Define grid sampler and build the variables and their distributions that it'll sample
    sampler = Grid("grid")
    self._add_snippet(sampler)
    vars, consts = self._create_sampler_variables(case, components)
    for sampled_var, vals in vars.items():
      sampler.add_variable(sampled_var)
      sampled_var.use_grid(construction="custom", type="value", values=sorted(vals))
    for var_name, val in consts.items():
      sampler.add_constant(var_name, val)

    # Number of "denoises" for the sampler is the number of samples it should take
    sampler.denoises = case.get_num_samples()

    # Add case labels to the sampler
    self._add_labels(sampler, case)

    # Print the results of the optimization
    print_results = PrintOutStream("sweep")
    print_results.source = results_data
    self._add_snippet(print_results)

    # Create a MultiRun step to run the sweep
    multirun = MultiRun("sweep")
    for inp in inputs:
      multirun.add_input(inp)
    multirun.add_model(model)
    multirun.add_sampler(sampler)
    multirun.add_output(results_data)
    multirun.add_output(print_results)
    self._add_snippet(multirun)

    # Add steps to the Sequence in RunInfo
    # FIXME: Dynamically figure out what order the steps should be in? (probably just leave it to the developer)
    self._add_step_to_sequence(multirun)

  def _opt_case(self, inputs: list[RavenSnippet], model: Model, case: Case, components: list[Component], sources: list[Placeholder]):
    """
    Sets up everything necessary for running an optimizer with "model" and outputting the results.
    @ In, inputs, list[RavenSnippet], list of inputs to add as Input nodes in the optimization MultiRun step
    @ In, model, Model, model to be optimized
    @ In, case, Case, HERON case object
    @ In, components, list[Component], HERON component objects
    @ In, sources, list[Placeholder], placeholder objects for data sources
    """
    # Fetch some helpful variable groups
    capacities_vargroup = self._template.find("VariableGroups/Group[@name='GRO_capacities']")
    results_vargroup = self._template.find("VariableGroups/Group[@name='GRO_outer_results']")

    # Create data objects for exporting optimization path and recording the points tried in the optimization
    solution_export = PointSet("opt_soln")
    solution_export.add_inputs("trajID")
    solution_export.add_outputs(["iteration", "accepted", capacities_vargroup, results_vargroup])
    self._add_snippet(solution_export)

    results_data = PointSet("opt_eval")
    results_data.add_inputs(capacities_vargroup)
    results_data.add_outputs(results_vargroup)
    self._add_snippet(results_data)

    # Define XML blocks for optimization: optimizer, sampler, ROM, etc.
    opt_strategy = case.get_opt_strategy()
    if opt_strategy == "BayesianOpt":
      optimizer = self._create_bayesian_opt(case, components, sources)
    elif opt_strategy == "GradientDescent":
      optimizer = self._create_gradient_descent(case, components, sources)
    else:
      raise ValueError(f"Template does not recognize optimization strategy {opt_strategy}.")

    # Set optimizer <TargetEvaluation> data object
    optimizer.set_target_data_object(results_data)

    # Set optimizer objective function
    objective = self._get_opt_metric_out_name(case)
    optimizer.objective = objective

    # Add case labels to the optimizer
    self._add_labels(optimizer, case)

    # Print the results of the optimization
    print_results = PrintOutStream("opt_soln")
    print_results.source = solution_export
    print_results.add_subelements(clusterLabel="trajID")
    self._add_snippet(print_results)

    # Create a MultiRun step to run the optimization
    multirun = MultiRun("optimize")
    for inp in inputs:
      multirun.add_input(inp)
    multirun.add_model(model)
    multirun.add_optimizer(optimizer)
    multirun.add_solution_export(solution_export)
    multirun.add_output(results_data)
    multirun.add_output(print_results)
    self._add_snippet(multirun)

    # Plot the result of the optimization
    opt_path_plot = OptPathPlot("opt_path")
    opt_path_plot.source = solution_export
    # opt_metric, _ = case.get_opt_metric()  # optimization metric name
    opt_path_plot.variables = ["GRO_capacities", objective]
    self._add_snippet(opt_path_plot)

    plot_step = IOStep(f"plot")
    plot_step.add_input(solution_export)
    plot_step.add_output(opt_path_plot)
    self._add_snippet(plot_step)

    # Add steps to the Sequence in RunInfo
    # FIXME: Dynamically figure out what order the steps should be in? (probably just leave it to the developer)
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
  def _initialize_runinfo(self, case: Case, case_name: str = "") -> RunInfo:
    """
    Initializes the RunInfo node of the workflow
    @ In, case, Case, the HERON Case object
    @ In, case_name, str, optional, the case name
    @ Out, run_info, RunInfo, a RunInfo object describing case run info
    """
    run_info = self._template.find("RunInfo")

    if case_name:
      run_info.job_name = case_name
      run_info.working_dir = case_name

    return run_info

  def _add_step_to_sequence(self, step: Step, index: int | None = None) -> None:
    sequence = find_node(self._template, "RunInfo/Sequence")
    sequence.add_step(step, index)

  def _get_step_index(self, step: Step | str) -> int | None:
    sequence = find_node(self._template, "RunInfo/Sequence")
    idx = sequence.get_step_index(step)
    return idx

  # Steps
  def _load_rom(self, source: Placeholder, rom: Model) -> IOStep:
    # Create the file input node
    file = File(source.name)
    file.text = source._target_file

    # create the IOStep
    step_name = self.namingTemplates["stepname"].format(action="read", subject=source.name)
    step = IOStep(step_name)
    step.append(file.to_assembler_node("Input"))
    step.append(rom.to_assembler_node("Output"))

    self._add_snippet(file)
    self._add_snippet(step)

    return step

  def _print_rom_meta(self, rom: Model) -> IOStep:
    """
    Create an IOStep to print the metadata for a ROM. Makes and adds the requisite DataSet and OutStream nodes.
    @ In, rom, Model, the ROM
    @ Out, step, IOStep, the IOStep
    """
    # Create the output data object
    dataset_name = f"{rom.name}_meta"
    dataset = DataSet(dataset_name)
    self._add_snippet(dataset)

    # Create the outstream for the dataset
    outstream = PrintOutStream(dataset_name)
    outstream.source = dataset
    self._add_snippet(outstream)

    # create step
    step_name = self.namingTemplates["stepname"].format(action="print_meta", subject=rom.name)
    step = IOStep(step_name)
    step.append(rom.to_assembler_node("Input"))
    step.append(dataset.to_assembler_node("Output"))
    step.append(outstream.to_assembler_node("Output"))
    self._add_snippet(step)

    return step

  def _csv_load_step(self, source: Placeholder) -> IOStep:
    pass

  # VariableGroups
  def _get_capacity_vars(self, case: Case, components: list[Component]) -> list[str]:
    """
    Collects component capacity and dispatch opt variable names to form a variable group
    @ In, case, Case, HERON case
    @ In, components, list[Component], HERON components
    @ Out, var_names, list[str], list of variable names
    """
    var_names = []  # list[str]
    # Add component opt vars
    for comp in components:
      comp_cap_type = comp.get_capacity(None, raw=True).type
      if comp_cap_type not in ["Function", "ARMA", "SyntheticHistory", "StaticHistory"]:
        var_names.append(f"{comp.name}_capacity")
    # Add dispatch opt vars
    for var in case.dispatch_vars.keys():
      var_names.append(f"{var}_dispatch")
    return var_names

  def _get_statistical_results_vars(self, case: Case, components: list[Component]) -> list[str]:
    """
    Collects result metric names for statistical metrics
    @ In, case, Case, HERON case
    @ In, components, list[Component], HERON components
    @ Out, var_names, list[str], list of variable names
    """
    # Add statistics for economic metrics to variable group. Use all statistics.
    default_names = self.DEFAULT_STATS_NAMES.get(case.get_mode(), [])
    # This gets the unique values from default_names and the case result statistics dict keys. Set operations
    # look cleaner but result in a randomly ordered list. Having a consistent ordering of statistics is beneficial
    # from a UX standpoint.
    stats_names = list(dict.fromkeys(default_names + list(case.get_result_statistics())))
    econ_metrics = case.get_econ_metrics(nametype="output")
    stats_var_names = self._get_result_statistic_names(econ_metrics, stats_names, case)

    # Add total activity statistics for variable group. Use only non-financial statistics.
    non_fin_stat_names = [name for name in stats_names if name not in self.FINANCIAL_STATS_NAMES]
    tot_activity_metrics = get_component_activity_vars(components, self.namingTemplates["tot_activity"])
    activity_var_names = self._get_result_statistic_names(tot_activity_metrics, non_fin_stat_names, case)

    var_names = stats_var_names + activity_var_names

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

  def _get_result_statistic_names(self, names: list[str], stats: list[str], case: Case):
    """
      Constructs the names of the statistics requested for output
      @ In, names, list[str], result metric names (economics, component activities)
      @ In, stats, list[str], statistic names
      @ In, case, HERON Case, defining Case instance
      @ Out, names, list, list of names of statistics requested for output
    """
    stat_prefixes = self._get_stat_prefixes(stats, case)
    stat_names = [f"{prefix}_{name}" for prefix, name in itertools.product(stat_prefixes, names)]
    return stat_names

  @staticmethod
  def _get_stat_prefixes(stat_names: list[str], case: Case) -> list[str]:
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

  # Models
  def _pickled_rom_from_source(self, source: Placeholder) -> PickledROM:
    rom = PickledROM(source.name)
    if source.needs_multiyear is not None:
      rom.add_subelements({"Multicycle" : {"cycles": source.needs_multiyear}})
    if source.limit_interp is not None:
      rom.add_subelements(maxCycles=source.limit_interp)
    self._add_snippet(rom)
    if source.eval_mode == 'clustered':
      ET.SubElement(rom, "clusterEvalMode").text = "clustered"
    return rom

  def _add_time_series_roms(self, case: Case, sources: list[Placeholder]):
    """
    Create and modify snippets based on sources
    @ In, case, Case, HERON case
    @ In, sources, list[Placeholder], case sources
    @ Out, None
    """
    ensemble_model = self._template.find("Models/EnsembleModel[@name='sample_and_dispatch']")
    dispatch_eval = self._template.find("DataObjects/DataSet[@name='dispatch_eval']")

    # Add models, steps, and their requisite data objects and outstreams for each case source
    arma_sources = (s for s in sources if s.is_type("ARMA"))
    for source in arma_sources:
      # An ARMA source is a pickled ROM that needs to be loaded.
      # Define the model node
      rom = self._pickled_rom_from_source(source)

      # Create an IOStep to load the model
      load_step = self._load_rom(source, rom)
      self._add_step_to_sequence(load_step, index=0)

      # Create an IOStep to print the ROM meta
      print_meta_step = self._print_rom_meta(rom)
      self._add_step_to_sequence(print_meta_step, index=1)

      # Add loaded ROM to the EnsembleModel
      inp_name = self.namingTemplates['data object'].format(source=source.name, contents='placeholder')
      inp_do = PointSet(inp_name)
      inp_do.add_inputs("scaling")
      self._add_snippet(inp_do)

      eval_name = self.namingTemplates['data object'].format(source=source.name, contents='samples')
      eval_do = DataSet(eval_name)
      eval_do.add_inputs("scaling")
      out_vars = source.get_variable()
      eval_do.add_outputs(out_vars)
      eval_do.add_index(case.get_time_name(), out_vars)
      eval_do.add_index(case.get_year_name(), out_vars)
      if source.eval_mode == "clustered":
        eval_do.add_index(self.namingTemplates['cluster_index'], out_vars)
      self._add_snippet(eval_do)

      # update variable group with ROM output variable names
      self._template.find("VariableGroups/Group[@name='GRO_dispatch_in_Time']").add_variables(*out_vars)

      rom_assemb = rom.to_assembler_node("Model")
      inp_do_assemb = inp_do.to_assembler_node("Input")
      eval_do_assemb = eval_do.to_assembler_node("TargetEvaluation")
      rom_assemb.append(inp_do.to_assembler_node("Input"))
      rom_assemb.append(eval_do.to_assembler_node("TargetEvaluation"))
      ensemble_model.append(rom_assemb)

      if source.eval_mode == "clustered":
        vg_dispatch = self._template.find("VariableGroups/Group[@name='GRO_dispatch']")
        vg_dispatch.add_variables(self.namingTemplates["cluster_index"])
        dispatch_eval.add_index(self.namingTemplates["cluster_index"], "GRO_dispatch_in_Time")

  @staticmethod
  def _add_stats_to_postprocessor(pp: EconomicRatioPostProcessor, names: list[str], vars: list[str], meta: dict[str, dict]) -> None:
    for var_name, stat_name in itertools.product(vars, names):
      prefix = meta[stat_name]["prefix"]
      pp.add_statistic(stat_name, prefix, var_name)

  # Distributions
  def _create_new_sampled_capacity(self, var_name, capacities):
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

  # Samplers
  def _create_sampler_variables(self, case, components) -> tuple[dict, dict]:
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
      vals = value.get_value(debug=case.debug["enabled"])  # FIXME refactor into separate debug mode
      if isinstance(vals, list):
        sampled_var = self._create_new_sampled_capacity(var_name, vals)
        sampled_variables[sampled_var] = vals

    # Make Distribution and SampledVariable objects for capacity variables. Capacities with non-parametric
    # ValuedParams are fixed values and are added instead as constants.
    for component in components:
      interaction = component.get_interaction()
      name = component.name
      var_name = self.namingTemplates["variable"].format(unit=name, feature="capacity")
      cap = interaction.get_capacity(None, raw=True)

      if not cap.is_parametric():  # we already know the value
        continue

      vals = cap.get_value(debug=case.debug["enabled"])  # FIXME: refactor debug mode into separate template
      if isinstance(vals, list):
        sampled_var = self._create_new_sampled_capacity(var_name, vals)
        sampled_variables[sampled_var] = vals
      else:  # it's a constant
        constants[var_name] = vals

    return sampled_variables, constants

  def _add_labels(self, sampler: Sampler, case: Case) -> None:
    """
    Add case labels as constants for a sampler or optimizer
    @ In, sampler, Sampler, sampler to add labels to
    @ In, case, Case, HERON case
    @ Out, None
    """
    for key, value in case.get_labels().items():
      var_name = self.namingTemplates["variable"].format(unit=key, feature="label")
      sampler.add_constant(var_name, value)

  # Optimizers
  def _create_bayesian_opt(self, case, components, sources) -> BayesianOptimizer:
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
      gpr.kernel = custom_kernel

    # Create sampler variables and their respective distributions
    vars, consts = self._create_sampler_variables(case, components)
    for sampled_var, vals in vars.items():
      sampled_var.use_grid(construction="grid", type="CDF", steps=10)
      optimizer.add_variable(sampled_var)
      sampler.add_variable(sampled_var)
    for var_name, val in consts.items():
      optimizer.add_constant(var_name, val)

    # Set number of denoises
    optimizer.denoises = case.get_num_samples()

    # Set GPR features list and target
    features = []
    for component in components:
      name = component.name
      interaction = component.get_interaction()
      cap = interaction.get_capacity(None, raw=True)
      if cap.is_parametric() and isinstance(cap.get_value(debug=case.debug['enabled']) , list):
        features.append(self.namingTemplates["variable"].format(unit=name, feature="capacity"))
    gpr.features = features
    gpr.target = self._get_opt_metric_out_name(case)

    # Create sampler constants, variables, and their distributions
    distributions = self._template.find("Distributions")
    # TODO

    return optimizer

  def _create_gradient_descent(self, case, components, sources):
    # Create necessary XML blocks
    optimizer = GradientDescent("cap_opt")
    self._add_snippet(optimizer)

    # Apply any specified optimization settings
    opt_settings = case.get_optimization_settings()
    optimizer.set_opt_settings(opt_settings)
    optimizer.objective = self._get_opt_metric_out_name(case)

    # Set number of denoises
    optimizer.denoises = case.get_num_samples()

    # Create sampler variables and their respective distributions
    vars, consts = self._create_sampler_variables(case, components)

    for sampled_var, vals in vars.items():
      # initial value
      min_val = min(vals)
      max_val = max(vals)
      delta = max_val - min_val
      # start 5% away from zero
      initial = min_val + 0.05 * delta if max_val > 0 else max_val - 0.05 * delta
      sampled_var.initial = initial
      optimizer.add_variable(sampled_var)

    for var_name, val in consts.items():
      optimizer.add_constant(var_name, val)

    return optimizer

  # Files
  def _get_function_files(self, sources) -> list[File]:
    # Add Function sources as Files
    files = []
    for function in [s for s in sources if s.is_type("Function")]:
      file = File(function.name)
      file.text = function._target_file
      self._add_snippet(file)
      files.append(file)
    return files

  @staticmethod
  def _get_opt_metric_out_name(case):
    """
      Constructs the output name of the metric specified as the optimization objective
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
      opt_out_metric_name = 'missing'

    return opt_out_metric_name
