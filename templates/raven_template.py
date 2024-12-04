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
from .snippets.models import Model, RavenCode, GaussianProcessRegressor, PickledROM
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
                             'distribution'   : '{unit}_{feature}_dist',
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
    if not isinstance(snippet, RavenSnippet):
      print("bad snippet:", snippet, type(snippet), snippet.tag)
      raise ValueError

    # If a parent node was provided, just append the snippet to its parent node.
    if isinstance(parent, ET.Element):
      parent.append(snippet)
      return

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

    # Define XML blocks for optimization: optimizer, sampler, ROM, etc.
    sampler = Grid("grid")
    self._add_sampler_variables(sampler, case, components, sources)  # TODO
    self._add_snippet(sampler)

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

    plot_step = IOStep(f"plot_{opt_path_plot.name}")
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

  # Steps
  def _load_rom(self, source: Placeholder, rom: Model) -> IOStep:
    rom_name = source.name
    rom_source = source._target_file

    # create the IOStep
    step_name = self.namingTemplates["stepname"].format(action="read", subject=rom_name)
    step = IOStep(step_name)
    step.append(self._assemblerNode("Input", "Files", "", rom_source))
    step.append(rom.to_assembler_node("Output"))

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

  def _create_new_capacity_variable(self, comp_name: str, var_name: str, capacities: str, sampler: Sampler):
    feature = "capacity" if "capacity" in var_name else "dispatch"

    # Create distribution
    dist_name = self.namingTemplates["distribution"].format(unit=comp_name, feature=feature)
    dist = Uniform(dist_name)
    dist.lower_bound = min(capacities)
    dist.upper_bound = max(capacities)

    # Create sampler variable
    # FIXME: This could be made more flexible to accommodate all RAVEN samplers. However, only a subset of
    #        RAVEN samplers are used at the moment (Grid, Stratified, MonteCarlo, Custom), so only these are
    #        supported here.
    sampler_var = SampledVariable(var_name)
    if isinstance(sampler, (Grid, Stratified, MonteCarlo)):
      sampler_var.distribution = dist
    if isinstance(sampler, (Grid, Stratified)):
      # TODO: where do these parameters come from?
      sampler_var.set_sampling_strategy(construction="equal", type="CDF", steps=4, values=[0, 1])

    # TODO: edit/add variable groups?_add_sampler_variables(sampler, case, components, sources)  # TODO

    return dist, sampler_var

  def _create_sampled_capacities(self, sampler: Sampler, distributions: ET.Element, components):
    for component in components:
      interaction = component.get_interaction()
      comp_name = component.name
      var_name = self.namingTemplates["variable"].format(unit=comp_name, feature="capacity")

      cap = interaction.get_capacity(None, raw=True)
      if not cap.is_parametric():
        continue

      vals = cap.get_value()  # debug mode not handled in this template!
      if isinstance(vals, list):
        # Create distribution and sampler variable nodes
        dist, sampler_var = self._create_new_capacity_variable(comp_name, var_name, vals, sampler)
        self._add_snippet(dist)
        sampler.append(sampler_var)

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
    return rom

  # Distributions
  def _create_uniform_variable(self, comp_name, var_name, capacities, sampler_type) -> tuple[Distribution, SampledVariable]:
    feature = "capacity" if "capacity" in var_name else "dispatch"
    dist_name = self.namingTemplates["distribution"].format(unit=comp_name, feature=feature)

    # create distribution snippet for the variable
    lower_bound = min(capacities)
    upper_bound = max(capacities)
    dist = Uniform(dist_name)
    dist.lower_bound = lower_bound
    dist.upper_bound = upper_bound

    # create variable for sampler, linked to the distribution
    sampler_var = SampledVariable(var_name)
    sampler_var.distribution = dist

    return dist, sampler_var

    # # Set how the sampler will sample the variable. This is determined by the mode and sampler type.
    # if sampler_type == "grid":  # just a grid sampler
    #   caps = " ".join([str(x) for x in sorted(capacities)])
    #   sampler_var.set_sampling_strategy(construction="custom", type="value", values=caps)
    # elif sampler_type == "opt":  # any optimization mode
    #   # initial value
    #   delta = upper_bound - lower_bound
    #   # start at 5% away from 0
    #   if upper_bound > 0:
    #     initial = lower_bound + 0.05 * delta
    #   else:
    #     initial = upper_bound - 0.05 * delta
    #   sampler_var.initial = initial

  # Samplers
  def _add_sampler_variables(self, sampler: Sampler, case, components, sources):
    # Add dispatch variables to sampler
    for key, value in case.dispatch_vars.items():
      var_name = self.namingTemplates["variable"].format(unit=key, feature="dispatch")
      vals = value.get_value(debug=case.debug["enabled"])  # FIXME refactor into separate debug mode
      if isinstance(vals, list):
        dist, sampler_var = self._create_uniform_variable(key, var_name, vals, "opt")  # FIXME
        self._add_snippet(dist)
        sampler.add_variable(sampler_var)

    # Add component capacity variables
    for component in components:
      interaction = component.get_interaction()
      name = component.name
      var_name = self.namingTemplates["variable"].format(unit=name, feature="capacity")
      cap = interaction.get_capacity(None, raw=True)

      if not cap.is_parametric():  # we already know the value
        continue

      vals = cap.get_value(debug=case.debug["enabled"])  # FIXME: refactor debug mode into separate template
      if isinstance(vals, list):
        dist, sampler_var = self._create_uniform_variable(name, var_name, vals, "opt")  # FIXME
        self._add_snippet(dist)
        if case.get_opt_strategy() == "BayesianOpt" and case.get_mode() == "opt" and not case.debug["enabled"]:  # TODO ugly
          # sampler_var.remove(sampler_var.find("initial"))  # FIXME: no subtractive XML operations!
          sampler_var.set_sampling_strategy(construction="equal", type="CDF", steps=10, values=[0, 1])
        sampler.add_variable(sampler_var)
      else:  # it's a constant
        sampler.add_constant(var_name, vals)

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
    optimizer = BayesianOptimizer("opt")
    sampler = Stratified("lhs")
    model = GaussianProcessRegressor("gpr")

    # Add blocks to XML template
    self._add_snippet(optimizer)
    self._add_snippet(sampler)
    self._add_snippet(model)

    # Connect optimizer to sampler and ROM components
    optimizer.set_sampler(sampler)
    optimizer.set_rom(model)

    # Apply any specified optimization settings
    opt_settings = case.get_optimization_settings()
    optimizer.set_opt_settings(opt_settings)
    # Set GPR kernel if provided
    if custom_kernel := opt_settings["algorithm"]["BayesianOpt"].get("kernel", None):
      model.kernel = custom_kernel

    # Create sampler variables and their respective distributions
    self._add_sampler_variables(sampler, case, components, sources)  # TODO

    # Set number of denoises
    # FIXME: same for all optimizers; refactor to be outside of BO method
    denoises = ET.SubElement(optimizer, "constant", name="denoises")
    denoises.text = case.get_num_samples()

    # Create sampler constants, variables, and their distributions
    distributions = self._template.find("Distributions")
    self._create_sampled_capacities(sampler, distributions, components)

    return optimizer

  def _create_gradient_descent(self, case, components, sources):
    # Create necessary XML blocks
    optimizer = GradientDescent("opt")
    self._add_snippet(optimizer)

    # Apply any specified optimization settings
    opt_settings = case.get_optimization_settings()
    optimizer.set_opt_settings(opt_settings)
    objective, _ = case.get_opt_metric()
    optimizer.objective = objective

    return optimizer

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
