import sys
import os
import shutil
import itertools

from templates.snippets.runinfo import RunInfo

from .raven_template import RavenTemplate
from .snippets.steps import MultiRun, PostProcess
from .snippets.variablegroups import VariableGroup
from .snippets.databases import NetCDF
from .snippets.dataobjects import DataSet, PointSet
from .snippets.models import EconomicRatioPostProcessor, EnsembleModel
from .snippets.outstreams import PrintOutStream, HeronDispatchPlot, TealCashFlowPlot
from .snippets.samplers import Sampler, MonteCarlo, SampledVariable

from .utils import get_capacity_vars, get_component_activity_vars

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
from HERON.src.Cases import Case
from HERON.src.Components import Component
from HERON.src.Placeholders import Placeholder
sys.path.pop()

# get raven location
RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))


class DebugTemplate(RavenTemplate):
  template_path = "debug.xml"
  write_name = "outer.xml"

  """ Sets up a flat RAVEN run for debug mode """
  def createWorkflow(self, case: Case, components: list[Component], sources: list[Placeholder]) -> None:
    super().createWorkflow(case, components, sources)

    self._update_vargroups(case, components, sources)
    self._update_dataset_indices(case)

    # Using a static history CSV or an ARMA ROM?
    #   - if ROM, copy ensemble model workflow from InnerTemplate
    #   - if CSV, add static CSV to XML, use CustomSampler to set up time series; not ensemble model needed
    has_arma_source = any(s.is_type("ARMA") for s in sources)
    has_csv_source = any(s.is_type("CSV") for s in sources)
    if has_arma_source and has_csv_source:
      raise ValueError("Mixing static CSVs and time series ROMs is not yet supported!")

    if has_arma_source:
      sampler = self._use_time_series_rom(case, components, sources)
    elif has_csv_source:
      sampler = self._use_static_csv(case, components, sources)
    else:
      raise ValueError("No time series sources found!")

    # Set number of samples for sampler
    sampler.denoises = case.get_num_samples()

    # Add capacities to sampler as constants
    capacity_vars = get_capacity_vars(components, self.namingTemplates["variable"], debug=True)
    for var_name, val in capacity_vars.items():
      sampler.add_constant(var_name, val)

    # Add optional plots
    debug_iostep = self._template.find("Steps/IOStep[@name='debug_output']")
    if case.debug["dispatch_plot"]:
      disp_plot = HeronDispatchPlot("dispatchPlot")
      disp_full_dataset = self._template.find("DataObjects/DataSet[@name='disp_full']")
      disp_plot.source = disp_full_dataset
      disp_plot.macro_variable = case.get_year_name()
      disp_plot.micro_variable = case.get_time_name()

      signals = set()
      for source in sources:
        new = source.get_variable()
        if new is not None:
          signals.update(set(new))
      disp_plot.signals = list(signals)

      self._add_snippet(disp_plot)
      debug_iostep.add_output(disp_plot)
    if case.debug["cashflow_plot"]:
      cashflow_plot = TealCashFlowPlot("cashflow_plot")
      cashflows = self._template.find("DataObjects/HistorySet[@name='cashflows']")
      cashflow_plot.source = cashflows
      self._add_snippet(cashflow_plot)
      debug_iostep.add_output(cashflow_plot)

  def _initialize_runinfo(self, case: Case, case_name: str = "") -> RunInfo:
    case_name = self.namingTemplates['jobname'].format(case=case.name, io='debug')
    run_info = super()._initialize_runinfo(case, case_name)

    # Use the outer parallel settings for flat run modes
    if case.outerParallel:
      # set outer batchsize and InternalParallel
      run_info.batch_size = case.outerParallel
      run_info.internal_parallel = True

    if case.useParallel:
      #XXX this doesn't handle non-mpi modes like torque or other custom ones
      run_info.set_parallel_run_settings(case.parallelRunInfo)

    if case.innerParallel:
      run_info.num_mpi = case.innerParallel

  def _use_time_series_rom(self, case: Case, components: list[Component], sources: list[Placeholder]) -> Sampler:
    # Create the ensemble model
    ensemble = EnsembleModel("sample_and_dispatch")
    self._add_snippet(ensemble)

    # Add Function sources as Files
    functions = self._get_function_files(sources)

    # Fetch the dispatch model and add it to the ensemble. The model and associated data objects already exist
    # in the template XML.
    dispatcher = self._template.find("Models/ExternalModel[@subType='HERON.DispatchManager']")
    dispatcher_assemb = dispatcher.to_assembler_node("Model")
    disp_placeholder = self._template.find("DataObjects/PointSet[@name='dispatch_placeholder']")
    disp_eval = self._template.find("DataObjects/DataSet[@name='dispatch_eval']")
    dispatcher_assemb.append(disp_placeholder.to_assembler_node("Input"))
    for func in functions:
      dispatcher_assemb.append(func.to_assembler_node("Input"))
    dispatcher_assemb.append(disp_eval.to_assembler_node("TargetEvaluation"))
    ensemble.append(dispatcher_assemb)

    # Load the time series ROM(s) from file and add to the ensemble model.
    self._add_time_series_roms(case, sources)  # Adds two IOStep for every ROM to load

    # Figure out econ metrics are being used for the case
    #   - econ metrics (from case obj), total activity variables (assembled from components list)
    #   - add to output groups GRO_dispatch_out, GRO_armasamples_out_scalar
    #   - add to metrics data object (arma_metrics PointSet)
    # TODO: refactor to function
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
    # TODO: refactor to function
    vg_final_return = self._template.find("VariableGroups/Group[@name='GRO_final_return']")
    results_vars = self._get_statistical_results_vars(case, components)
    vg_final_return.add_variables(*results_vars)

    # Fill out statistics to be calculated by the postprocessor
    # TODO: refactor to function
    pp = EconomicRatioPostProcessor("statistics")
    self._add_snippet(pp)
    default_names = self.DEFAULT_STATS_NAMES.get(case.get_mode(), [])
    stats_names = list(dict.fromkeys(default_names + list(case.get_result_statistics())))
    self._add_stats_to_postprocessor(pp, stats_names, econ_vars, case.stats_metrics_meta)
    # Activity metrics with non-financial statistics
    non_fin_stat_names = [name for name in stats_names if name not in self.FINANCIAL_STATS_NAMES]
    self._add_stats_to_postprocessor(pp, non_fin_stat_names, activity_vars, case.stats_metrics_meta)

    # A MonteCarlo sampler is used to sample from the time series ROM. Capacity values will be added as constants
    # in the createWorkflow method.
    mc = MonteCarlo("mc")
    mc.add_constant("scaling", 1.0)
    self._add_snippet(mc)

    ###############
    # Steps Setup #
    ###############
    # The template XML already has the debug MultiRun and debug_output IOStep steps in the sequence.

    # Add the model, sampler, file inputs to the main multirun step
    multirun = self._template.find("Steps/MultiRun[@name='debug']")
    multirun.add_model(ensemble)
    multirun.add_sampler(mc)
    for func in functions:
      multirun.add_input(func)

    # Add an EconomicRatio postprocessor and a postprocess step to summarize the econ results.
    arma_metrics = self._template.find("DataObjects/PointSet[@name='arma_metrics']")
    metrics_stats = self._template.find("DataObjects/PointSet[@name='metrics_stats']")
    pp_step = PostProcess("summarize")
    pp_step.add_input(arma_metrics)
    pp_step.add_model(pp)
    pp_step.add_output(metrics_stats)
    self._add_snippet(pp_step)

    # We need to be careful to add the "summarize" step after the "debug" MultiRun
    debug_idx = self._get_step_index(multirun)
    self._add_step_to_sequence(pp_step, index=debug_idx+1)

    return mc

  def _use_static_csv(self, case: Case, components: list[Component], sources: list[Placeholder]) -> Sampler:
    raise NotImplementedError

  def _update_vargroups(self, case, components, sources):
    # Fill out capacities vargroup
    capacities_vargroup = self._template.find("VariableGroups/Group[@name='GRO_capacities']")
    capacities_vars = list(get_capacity_vars(components, self.namingTemplates["variable"]))
    capacities_vargroup.add_variables(*capacities_vars)

    # Add time indices to GRO_time_indices
    self._template.find("VariableGroups/Group[@name='GRO_time_indices']").add_variables(
      case.get_time_name(),
      case.get_year_name()
    )

    # expected dispatch, ARMA outputs
    # -> dispatch results
    group = self._template.find("VariableGroups/Group[@name='GRO_outer_debug_dispatch']")
    for component in components:
      name = component.name
      for tracker in component.get_tracking_vars():
        resource_list = sorted(list(component.get_resources()))
        for resource in resource_list:
          var_name = self.namingTemplates['dispatch'].format(component=name, tracker=tracker, resource=resource)
          group.add_variables(var_name)

    group = self._template.find("VariableGroups/Group[@name='GRO_cashflows']")
    cfs = self._find_cashflows(components)
    group.add_variables(*cfs)

    # -> synthetic histories?
    group = self._template.find("VariableGroups/Group[@name='GRO_outer_debug_synthetics']")
    for source in sources:
      if source.is_type('ARMA') or source.is_type('CSV'):
        synths = source.get_variable()
        group.add_variables(*synths)

  def _update_dataset_indices(self, case: Case) -> None:
    # Configure dispatch DataSet indices
    time_name = case.get_time_name()
    year_name = case.get_year_name()
    cluster_name = self.namingTemplates["cluster_index"]

    for time_index in self._template.findall(".//DataSet/Index[@var='Time']"):
      time_index.set("var", time_name)

    for year_index in self._template.findall(".//DataSet/Index[@var='Year']"):
      year_index.set("var", year_name)

    for cluster_index in self._template.findall(".//DataSet/Index[@var='_ROM_Cluster']"):
      cluster_index.set("var", cluster_name)

  @staticmethod
  def _find_cashflows(components):
    """
      Loop through comps and collect all the full cashflow names
      @ In, components, list, list of HERON Component instances for this run
      @ Out, cfs, list, list of cashflow full names e.g. {comp}_{cf}_CashFlow
    """
    cfs = []
    for comp in components:
      comp_name = comp.name
      for cashflow in comp.get_cashflows():
        # User has specified to leave this cashflow out of the NPV calculation. Skip it.
        if cashflow.is_npv_exempt():
          continue
        cf_name = cashflow.name
        name = f'{comp_name}_{cf_name}_CashFlow'
        cfs.append(name)
        if cashflow._depreciate is not None:
          cfs.append(f'{comp_name}_{cf_name}_depreciation')
          cfs.append(f'{comp_name}_{cf_name}_depreciation_tax_credit')
    return cfs
