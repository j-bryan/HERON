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
from .snippets.samplers import SamplerVariable

from .utils import get_capacity_vars, get_component_activity_vars

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
from HERON.src.Cases import Case
from HERON.src.Components import Component
from HERON.src.Placeholders import Placeholder
sys.path.pop()


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

    # Create slave RAVEN model. This gets loaded from the template, since all bilevel workflows use this.
    raven = self._raven_model(case, components)

    # Get any inputs to the sweep/opt MultiRun step. In this case, we need to look for a few files.
    inputs = self._template.findall("Files/Input")

    # Set up some helpful variable groups
    capacities_vargroup = self._template.find("VariableGroups/Group[@name='GRO_capacities']")
    capacities_vars = list(get_capacity_vars(components, self.namingTemplates["variable"]))
    capacities_vargroup.add_variables(*capacities_vars)

    results_vargroup = self._template.find("VariableGroups/Group[@name='GRO_outer_results']")
    results_vars = self._get_statistical_results_vars(case, components)
    results_vargroup.add_variables(*results_vars)

    # Define the sweep or optimize MultiRun steps and its necessary optimizers, samplers, data objects, etc.
    if case.get_mode() == "sweep":
      self._sweep_case(inputs, raven, case, components, sources)
    elif case.get_mode() == "opt":
      self._opt_case(inputs, raven, case, components, sources)
    else:
      # Shouldn't ever reach here, but I wanted to be explicit in which case modes are handled instead of using an
      # else block in the case mode check control flow above.
      raise ValueError(f"Case mode '{case.get_mode()}' is not supported for OuterTemplate templates.")

  def set_inner_data_name(self, name: str, inner_to_outer: str) -> None:
    model = self._template.find("Models/Code[@subType='RAVEN']")
    model.set_inner_data_handling(name, inner_to_outer)

  def _initialize_runinfo(self, case: Case) -> None:
    """
    Initializes the RunInfo node of the workflow
    @ In, case, Case, the HERON Case object
    @ Out, None
    """
    case_name = case_name = self.namingTemplates['jobname'].format(case=case.name, io='o')
    run_info = super()._initialize_runinfo(case, case_name)

    # parallel
    if case.outerParallel:
      # set outer batchsize and InternalParallel
      run_info.batch_size = case.outerParallel
      run_info.internal_parallel = True

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
    capacities_vargroup.add_variables(*list(capacities_vars))
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
    self._template.find("VariableGroups/Group[@name='GRO_init_disp']").add_variables(*dispatch_vars)
    self._template.find("VariableGroups/Group[@name='GRO_full_dispatch']").add_variables(*dispatch_vars)
    self._template.find("VariableGroups/Group[@name='GRO_capacities']").add_variables(*dispatch_vars)

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
    self._template.find("VariableGroups/Group[@name='GRO_dispatch_out']").add_variables(*output_vars)
    self._template.find("VariableGroups/Group[@name='GRO_armasamples_out_scalar']").add_variables(*output_vars)
    self._template.find("DataObjects/PointSet[@name='arma_metrics']").add_outputs(*output_vars)

    # Figure out what result statistics are being used
    #   - outer product of ({econ metrics (NPV, IRR, etc.)} U {activity variables "TotalActivity_*"}) x {statistics to use (mean, std, etc.)}
    #     - NOTE: this part looks about identical to what was done in the outer
    #     - Add these variables to GRO_final_return
    #     - Make sure the objective function metric is in this group
    #   - fill out econ post processor model
    #     - format: <statName prefix="{abbrev}">variable name</statName>; can have additional "percent" or "threshold" attrib
    #     - skip financial metrics (valueAtRisk, expectedShortfall, etc) for any TotalActivity* variable
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
    step_name = self.namingTemplates["stepname"].format(action="write", subject=metrics_stats.name)
    write_metrics_stats = self._template.find(f"Steps/IOStep[@name='{step_name}']")
    self._dispatch_results_name = "disp_results"
    data_handling = case.data_handling["inner_to_outer"]
    if data_handling == "csv":
      disp_results = PrintOutStream(self._dispatch_results_name)
      disp_results.set_source(metrics_stats)
    else:  # default to NetCDF handling
      disp_results = NetCDF(self._dispatch_results_name)
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

  def _add_case_labels_to_sampler(self, case_labels: dict[str, str]) -> None:
    """
    Adds case labels to relevant variable groups
    @ In, case_labels, dict[str, str], the case labels
    @ Out, None
    """
    if not case_labels:
      return

    mc = self._template.find("Samplers/MonteCarlo[@name='mc']")
    vg_case_labels = VariableGroup("GRO_case_labels")
    self._template.find("VariableGroups/Group[@name='GRO_armasamples_in_scalar']").add_variables(vg_case_labels.name)
    self._template.find("VariableGroups/Group[@name='GRO_dispatch_in_scalar']").add_variables(vg_case_labels.name)
    for k, label_val in case_labels.items():
      label_name = self.namingTemplates["variable"].format(unit=k, feature="label")
      vg_case_labels.add_variables(label_name)
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
      group.add_variables(time_name, year_name)

    for time_index in self._template.findall("DataObjects/DataSet/Index[@var='Time']"):
      time_index.set("var", time_name)

    for year_index in self._template.findall("DataObjects/DataSet/Index[@var='Year']"):
      year_index.set("var", year_name)

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
      # self._add_model_to_ensemble(rom, ensemble_model)
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
      self._add_snippet(eval_do)

      rom_assemb = rom.to_assembler_node("Model")
      rom_assemb.append(inp_do.to_assembler_node("Input"))
      rom_assemb.append(eval_do.to_assembler_node("TargetEvaluation"))
      ensemble_model.append(rom_assemb)

      if source.eval_mode == "clustered":
        vg_dispatch = self._template.find("VariableGroups/Group[@name='GRO_dispatch']")
        vg_dispatch.add_variables(self.namingTemplates["cluster_index"])
        dispatch_eval.add_index(self.namingTemplates["cluster_index"], "GRO_dispatch_in_Time")

  def _add_uncertain_cashflow_params(self, components) -> None:
    cf_attrs = ["_driver", "_alpha", "_reference", "_scale"]

    vg_econ_uq = self._template.find("VariableGroups/Group[@name='GRO_econ_UQ']")
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
        dist_name = self.namingTemplates["distribution"].format(unit=unit_name, feature=feature_name)
        feat_name = self.namingTemplates["variable"].format(unit=unit_name, feature=feature_name)

        dist_node = vp._vp.get_distribution() #ugh, this is NOT the XML... will have to reconstruct.
        dist_node.set("name", dist_name)
        print(f"{dist_node=}")
        dist_snippet = snippet_factory.from_xml(dist_node)
        print(f"{dist_snippet=}")
        self._add_snippet(dist_snippet)  # added to Distributions

        # Add uncertain parameter to econ UQ variable group
        vg_econ_uq.add_variables(feat_name)

        # Add distribution to MonteCarlo sampler
        sampler_var = SamplerVariable(feat_name)
        sampler_var.set_distribution(dist_snippet)
        mc.add_variable(sampler_var)

  @staticmethod
  def _add_stats_to_postprocessor(pp: EconomicRatioPostProcessor, names: list[str], vars: list[str], meta: dict[str, dict]) -> None:
    # for stat_name, var_name in itertools.product(names, vars):
    for var_name, stat_name in itertools.product(vars, names):
      stat_meta = meta[stat_name]
      prefix = stat_meta["prefix"]
      stat_attribs = {k: stat_meta[k] for k in stat_meta.keys() & {"percent", "threshold"}}

      for k, v in stat_attribs.items():
        if isinstance(v, list):
          for vi in v:
            pp.add_statistic(stat_name, prefix, var_name, **{k: vi})
        else:
            pp.add_statistic(stat_name, prefix, var_name, **{k: v})
      else:
        pp.add_statistic(stat_name, prefix, var_name)
