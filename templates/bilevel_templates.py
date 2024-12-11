import sys
import os
import shutil
import itertools

from .raven_template import RavenTemplate
from .snippets.factory import factory as snippet_factory
from .snippets.variablegroups import VariableGroup
from .snippets.databases import NetCDF
from .snippets.dataobjects import DataSet, PointSet
from .snippets.models import RavenCode, EconomicRatioPostProcessor
from .snippets.outstreams import PrintOutStream
from .snippets.samplers import SampledVariable, Sampler

from .utils import get_capacity_vars, get_component_activity_vars

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
from HERON.src.Cases import Case
from HERON.src.Components import Component
from HERON.src.Placeholders import Placeholder
sys.path.pop()

# get raven location
RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))


class BilevelTemplate(RavenTemplate):
  """ Coordinates information between inner and outer templates for bilevel workflows """
  def __init__(self):
    super().__init__()
    self.inner = InnerTemplate()
    self.outer = OuterTemplate()

  def loadTemplate(self) -> None:
    self.inner.loadTemplate()
    self.outer.loadTemplate()

  def createWorkflow(self, case: Case, components: list[Component], sources: list[Placeholder]) -> None:
    self.inner.createWorkflow(case, components, sources)
    self.outer.createWorkflow(case, components, sources)

    # Coordinate across templates. The outer workflow needs to know where the inner workflow will save the dispatch
    # results to perform additional processing.
    disp_results_name = self.inner.get_dispatch_results_name()
    self.outer.set_inner_data_name(disp_results_name, case.data_handling["inner_to_outer"])

  def writeWorkflow(self, destination: str, case: Case, components: list[Component], sources: list[Placeholder]) -> None:
    self.outer.writeWorkflow(destination, case, components, sources)
    self.inner.writeWorkflow(destination, case, components, sources)

    # copy "write_inner.py", which has the denoising and capacity fixing algorithms
    write_inner_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    conv_src = os.path.abspath(os.path.join(write_inner_dir, 'write_inner.py'))
    conv_file = os.path.abspath(os.path.join(destination, 'write_inner.py'))
    shutil.copyfile(conv_src, conv_file)
    msg_format = 'Wrote "{1}" to "{0}/"'
    print(msg_format.format(*os.path.split(conv_file)))

class OuterTemplate(RavenTemplate):
  template_path = "outer.xml"
  write_name = "outer.xml"

  def createWorkflow(self, case: Case, components: list[Component], sources: list[Placeholder]) -> None:
    super().createWorkflow(case, components, sources)

    # Add Function sources as Files
    self._get_function_files(sources)

    # Create slave RAVEN model. This gets loaded from the template, since all bilevel workflows use this.
    raven = self._raven_model(case, components)

    # Get any inputs to the sweep/opt MultiRun step. In this case, we need to look for a few files.
    inputs = self._template.findall("Files/Input")

    # Set up some helpful variable groups
    capacities_vargroup = self._template.find("VariableGroups/Group[@name='GRO_capacities']")
    capacities_vars = list(get_capacity_vars(components, self.namingTemplates["variable"]))
    capacities_vargroup.variables.extend(capacities_vars)

    results_vargroup = self._template.find("VariableGroups/Group[@name='GRO_outer_results']")
    results_vars = self._get_statistical_results_vars(case, components)
    results_vargroup.variables.extend(results_vars)

    # Define the sweep or optimize MultiRun steps and its necessary optimizers, samplers, data objects, etc.
    if case.get_mode() == "sweep":
      self._sweep_case(inputs, raven, case, components, sources)
    elif case.get_mode() == "opt":
      self._opt_case(inputs, raven, case, components, sources)
    else:
      # Shouldn't ever reach here, but I wanted to be explicit in which case modes are handled instead of using an
      # else block in the case mode check control flow above.
      raise ValueError(f"Case mode '{case.get_mode()}' is not supported for OuterTemplate templates.")

    # Update the parallel settings based on the number of sampled variables if the number of outer parallel runs
    # was not specified before.
    if case.outerParallel == 0 and case.useParallel:
      self._update_batch_size(case)

  def set_inner_data_name(self, name: str, inner_to_outer: str) -> None:
    model = self._template.find("Models/Code[@subType='RAVEN']")
    model.set_inner_data_handling(name, inner_to_outer)

  def _initialize_runinfo(self, case: Case) -> None:
    """
    Initializes the RunInfo node of the workflow
    @ In, case, Case, the HERON Case object
    @ Out, None
    """
    case_name = self.namingTemplates['jobname'].format(case=case.name, io='o')
    run_info = super()._initialize_runinfo(case, case_name)

    # parallel
    if case.outerParallel:
      # set outer batchsize and InternalParallel
      run_info.batch_size = case.outerParallel
      run_info.internal_parallel = True
    else:
      run_info.batch_size = 1

    if case.useParallel:
      #XXX this doesn't handle non-mpi modes like torque or other custom ones
      run_info.set_parallel_run_settings(case.parallelRunInfo)

    if case.innerParallel:
      run_info.num_mpi = case.innerParallel

  def _raven_model(self, case: Case, components: list[Component]) -> RavenCode:
    """
    Configures the inner RAVEN code. The bilevel outer template MUST have a <Code subType="RAVEN"> node defined.
    """
    raven = self._template.find("Models/Code[@subType='RAVEN']")

    # Find the RAVEN executable to use
    exec_path = os.path.abspath(os.path.join(RAVEN_LOC, "..", "raven_framework"))
    if os.path.exists(exec_path):
      executable = exec_path
    elif shutil.which("raven_ravemework" is not None):
      executable = "raven_framework"
    else:
      raise RuntimeError(f"raven_framework not in PATH and not at {exec_path}")
    raven.executable = executable

    # custom python command for running raven (for example, "coverage run")
    if cmd := case.get_py_cmd_for_raven():
      raven.set_py_cmd(cmd)

    # Add variable aliases for Inner
    for component in components:
      raven.add_alias(component.name, suffix="capacity")

    # Add label aliases for Inner
    for label in case.get_labels():
      raven.add_alias(label, suffix="label")

    return raven

  def _update_batch_size(self, case: Case) -> None:
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

class InnerTemplate(RavenTemplate):
  """ Template for the inner workflow of a bilevel problem """
  template_path = "inner.xml"
  write_name = "inner.xml"

  def __init__(self):
    super().__init__()
    self._dispatch_results_name = ""  # str, keeps track of the name of the Database or OutStream used pass dispatch
                                      #      data to the outer workflow

  def createWorkflow(self, case: Case, components: list[Component], sources: list[Placeholder]) ->  None:
    super().createWorkflow(case, components, sources)

    # Add ARMA ROMs to ensemble model
    #   - create pickled ROM for ARMA ROM
    #     - model node
    #   - load & print steps for pickled ROM
    #     - iostep to load from file into rom node
    #     - dataobject to hold rom meta, outstream to print it, and an iostep to make it happen
    #   - add ROM to ensemble model
    #     - input (placeholder) & output data objects for sampling
    #     - add ROM as assembler node to ensemble model
    self._add_time_series_roms(case, sources)

    # Determine which variables are sampled by the Monte Carlo sampler
    mc = self._template.find("Samplers/MonteCarlo[@name='mc_arma_dispatch']")
    #   - component capacities (constants)
    #     - add variables to GRO_capacities
    capacities_vargroup = self._template.find("VariableGroups/Group[@name='GRO_capacities']")
    capacities_vars = get_capacity_vars(components, self.namingTemplates["variable"])
    capacities_vargroup.variables.extend(list(capacities_vars))
    for k, v in capacities_vars.items():
      val = "" if isinstance(v, list) else v  # empty string is overwritten by capacity from outer in write_inner.py
      mc.add_constant(k, val)

    # Add case labels to sampler and variable groups, if any labels have been provided
    #   - case labels (constants)
    #     - make case_labels variable group
    #     - case labels group to input variable groups (armasamples_in_scalar, dispatch_in_scalar)
    #     - add constants to MC sampler
    self._add_case_labels_to_sampler(case.get_labels())

    # Add dispatch variables to GRO_init_disp, GRO_full_dispatch
    dispatch_vars = get_component_activity_vars(components, self.namingTemplates["dispatch"])
    self._template.find("VariableGroups/Group[@name='GRO_init_disp']").variables.extend(dispatch_vars)
    self._template.find("VariableGroups/Group[@name='GRO_full_dispatch']").variables.extend(dispatch_vars)

    # Set time variable names
    #   - add time index names in all DataSet objects (replacing "Time", "Year" default names)
    #   - add time variable names to GRO_time_indices
    self._set_time_vars(case.get_time_name(), case.get_year_name())

    # See if there are any uncertain cashflow parameters that need to get added to the sampler
    self._add_uncertain_cashflow_params(components)

    # Figure out econ metrics are being used for the case
    #   - econ metrics (from case obj), total activity variables (assembled from components list)
    #   - add to output groups GRO_dispatch_out, GRO_armasamples_out_scalar
    #   - add to metrics data object (arma_metrics PointSet)
    activity_vars = get_component_activity_vars(components, self.namingTemplates["tot_activity"])
    econ_vars = case.get_econ_metrics(nametype="output")
    output_vars = econ_vars + activity_vars
    self._template.find("VariableGroups/Group[@name='GRO_dispatch_out']").variables.extend(output_vars)
    self._template.find("VariableGroups/Group[@name='GRO_armasamples_out_scalar']").variables.extend(output_vars)
    self._template.find("DataObjects/PointSet[@name='arma_metrics']").outputs.extend(output_vars)

    # Figure out what result statistics are being used
    #   - outer product of ({econ metrics (NPV, IRR, etc.)} U {activity variables "TotalActivity_*"}) x {statistics to use (mean, std, etc.)}
    #     - NOTE: this part looks about identical to what was done in the outer
    #     - Add these variables to GRO_final_return
    #     - Make sure the objective function metric is in this group
    #   - fill out econ post processor model
    #     - format: <statName prefix="{abbrev}">variable name</statName>; can have additional "percent" or "threshold" attrib
    #     - skip financial metrics (valueAtRisk, expectedShortfall, etc) for any TotalActivity* variable
    vg_final_return = self._template.find("VariableGroups/Group[@name='GRO_final_return']")
    results_vars = self._get_statistical_results_vars(case, components)
    vg_final_return.variables.extend(results_vars)

    econ_pp = self._template.find("Models/PostProcessor[@name='statistics']")
    # Econ metrics with all statistics names
    # NOTE: This logic is borrowed from RavenTemplate._get_statistical_results_vars, but it's more useful to have the names,
    # prefixes, and variable name separate here, not as one big string. Otherwise, we have to try to break that string
    # back up, which would be sensitive to metric and variable naming conventions. We duplicate a little of the logic but
    # get something more robust in return.
    default_names = self.DEFAULT_STATS_NAMES.get(case.get_mode(), [])
    stats_names = list(dict.fromkeys(default_names + list(case.get_result_statistics())))
    self._add_stats_to_postprocessor(econ_pp, stats_names, econ_vars, case.stats_metrics_meta)
    # Activity metrics with non-financial statistics
    non_fin_stat_names = [name for name in stats_names if name not in self.FINANCIAL_STATS_NAMES]
    self._add_stats_to_postprocessor(econ_pp, non_fin_stat_names, activity_vars, case.stats_metrics_meta)

    # Work out how the inner results should be routed back to the outer
    #    - database or csv
    metrics_stats = self._template.find("DataObjects/PointSet[@name='metrics_stats']")
    write_metrics_stats = self._template.find(f"Steps/IOStep[@name='database']")
    self._dispatch_results_name = "disp_results"
    data_handling = case.data_handling["inner_to_outer"]
    if data_handling == "csv":
      disp_results = PrintOutStream(self._dispatch_results_name)
      disp_results.source = metrics_stats
    else:  # default to NetCDF handling
      disp_results = NetCDF(self._dispatch_results_name)
      disp_results.read_mode = "overwrite"
    self._add_snippet(disp_results)
    write_metrics_stats.add_output(disp_results)

  def get_dispatch_results_name(self) -> str:
    """
    Gets the name of the Database or OutStream used to export the dispatch results to the outer workflow
    @ In, inner_to_outer, str, one of "csv" or "netcdf"
    @ Out, disp_results_name, str, the name of the dispatch results object
    """
    if not self._dispatch_results_name:
      raise ValueError("No dispatch results object name has been set! Perhaps the inner workflow hasn't been created yet?")
    return self._dispatch_results_name

  def _initialize_runinfo(self, case: Case) -> None:
    # Called by the RavenTemplate class, no need ot add to this class's createWorkflow method.
    case_name = case_name = self.namingTemplates["jobname"].format(case=case.name, io="i")
    run_info = super()._initialize_runinfo(case, case_name)

    # parallel settings
    if case.innerParallel:
      run_info.internal_parallel = True
      run_info.batch_size = case.innerParallel
    else:
      run_info.batch_size = 1

  def _add_case_labels_to_sampler(self, case_labels: dict[str, str]) -> None:
    """
    Adds case labels to relevant variable groups
    @ In, case_labels, dict[str, str], the case labels
    @ Out, None
    """
    if not case_labels:
      return

    mc = self._template.find("Samplers/MonteCarlo[@name='mc_arma_dispatch']")
    vg_case_labels = VariableGroup("GRO_case_labels")
    self._template.find("VariableGroups/Group[@name='GRO_armasamples_in_scalar']").variables.append(vg_case_labels.name)
    self._template.find("VariableGroups/Group[@name='GRO_dispatch_in_scalar']").variables.append(vg_case_labels.name)
    for k, label_val in case_labels.items():
      label_name = self.namingTemplates["variable"].format(unit=k, feature="label")
      vg_case_labels.variables.append(label_name)
      mc.add_constant(label_name, label_val)

  def _set_time_vars(self, time_name: str, year_name: str) -> None:
    """
    Update variable groups and data objects to have the correct time variable names.
    @ In, time_name, str, name of time variable
    @ In, year_name, str, name of year variable
    @ Out, None
    """
    for vg in ["GRO_dispatch", "GRO_full_dispatch_indices"]:
      group = self._template.find(f"VariableGroups/Group[@name='{vg}']")
      group.variables.extend([time_name, year_name])

    for time_index in self._template.findall("DataObjects/DataSet/Index[@var='Time']"):
      time_index.set("var", time_name)

    for year_index in self._template.findall("DataObjects/DataSet/Index[@var='Year']"):
      year_index.set("var", year_name)

  def _add_uncertain_cashflow_params(self, components) -> None:
    cf_attrs = ["_driver", "_alpha", "_reference", "_scale"]

    vg_econ_uq = self._template.find("VariableGroups/Group[@name='GRO_econ_UQ']")
    if vg_econ_uq is None:
      vg_econ_uq = VariableGroup("GRO_econ_UQ")
    mc = self._template.find("Samplers/MonteCarlo[@name='mc_arma_dispatch']")

    # looping through components to find uncertain cashflow attributes
    for component in components:
      comp_name = component.name
      # this is gonna be gross
      cfs = component.get_cashflows()

      for cf, attr in itertools.product(cfs, cf_attrs):
        vp = getattr(cf, attr)
        if vp.type != "RandomVariable":
          continue

        unit_name = f"{comp_name}_{cf.name}"
        feature_name = attr.rsplit("_", 1)[1]
        feat_name = self.namingTemplates["variable"].format(unit=unit_name, feature=feature_name)
        dist_name = self.namingTemplates["distribution"].format(variable=feat_name)

        dist_node = vp._vp.get_distribution() #ugh, this is NOT the XML... will have to reconstruct.
        dist_node.set("name", dist_name)
        dist_snippet = snippet_factory.from_xml(dist_node)
        self._add_snippet(dist_snippet)  # added to Distributions

        # Add uncertain parameter to econ UQ variable group
        vg_econ_uq.variables.append(feat_name)

        # Add distribution to MonteCarlo sampler
        sampler_var = SampledVariable(feat_name)
        sampler_var.distribution = dist_snippet
        mc.add_variable(sampler_var)

    if len(vg_econ_uq.variables):
      self._add_snippet(vg_econ_uq)
