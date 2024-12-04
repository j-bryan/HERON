import sys
import os
import shutil
import itertools

from .raven_template import RavenTemplate
from .snippets.factory import factory as snippet_factory
from .snippets.files import File
from .snippets.variablegroups import VariableGroup
from .snippets.databases import NetCDF
from .snippets.dataobjects import DataSet, PointSet
from .snippets.models import Model, RavenCode, EconomicRatioPostProcessor, EnsembleModel, ExternalModel
from .snippets.outstreams import PrintOutStream
from .snippets.samplers import MonteCarlo, SamplerVariable

from .utils import get_capacity_vars, get_component_activity_vars
from .xml_utils import find_node, get_node_index

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

  def createWorkflow(self, case, components, sources) -> None:
    self.inner.createWorkflow(case, components, sources)
    self.outer.createWorkflow(case, components, sources)

    # Coordinate across templates. The outer workflow needs to know where the inner workflow will save the dispatch
    # results to perform additional processing.
    disp_results_name = self.inner.get_dispatch_results_name()
    self.outer.set_inner_data_name(disp_results_name, case.data_handling["inner_to_outer"])

  def writeWorkflow(self, destination, case, components, sources) -> None:
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
  template_path = "xml/bilevel_outer.xml"
  write_name = "outer.xml"

  def createWorkflow(self, case, components, sources) -> None:
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

  def _raven_model(self, case, components) -> RavenCode:
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
  template_path = "xml/bilevel_inner.xml"
  write_name = "inner.xml"

  def __init__(self):
    super().__init__()
    self._dispatch_results_name = ""  # str, keeps track of the name of the Database or OutStream used pass dispatch
                                      #      data to the outer workflow

  # def createWorkflow(self, case, components, sources) ->  None:
  #   super().createWorkflow(case, components, sources)
  #   # FIXME Assume synthetic histories for now but could be multiple static histories

  #   # Collect relevant variables before we start adding names/parameters/nodes to various parts of the XML
  #   cap_vars = get_capacity_vars(components, self.namingTemplate["variable"])  # dict[str, valued param]
  #   disp_vars = get_dispatch_vars(components, self.namingTemplates["dispatch"])  # list[str]

  #   # Fill out variable names for final_return variable group
  #   results_vargroup = self._template.find("GRO_final_return")
  #   results_vars = self._get_statistical_results_vars(case, components)
  #   results_vargroup.add_variables(*results_vars)

  #   # For all ARMA sources, create a model node for the accompanying pickled ROM, add that ROM to the ensemble model,
  #   # and create steps to load the model and write its metadata.
  #   self._add_time_series_roms(case, sources)

  #   # For
  #   self._modify_components(case, components)
  #   self._modify_case_labels(case.get_labels())
  #   self._modify_time_vars(case.get_time_name(), case.get_year_name())
  #   self._modify_econ_metrics(case, components)
  #   self._modify_result_statistics(case, components)

  def createWorkflow(self, case, components, sources) ->  None:
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
    stats_names = set(default_names) | set(case.get_result_statistics())
    self._add_stats_to_postprocessor(econ_pp, stats_names, econ_vars, case.stats_metrics_meta)
    # Activity metrics with non-financial statistics
    non_fin_stat_names = stats_names - set(self.FINANCIAL_STATS_NAMES)
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

  def _modify_components(self, case: Case, components: list[Component]):
    """
    Modify variable groups and the Monte Carlo sampler to include capacity and dispatch variables
    """
    mc = self._template.find("Samplers/MonteCarlo[@name='mc_arma_dispatch']")
    vg_capacities = self._template.find("VariableGroups/Group[@name='GRO_capacities']")
    vg_init_disp = self._template.find("VariableGroups/Group[@name='GRO_init_disp']")
    vg_full_disp = self._template.find("VariableGroups/Group[@name='GRO_full_dispatch']")

    # change inner input due to components requested
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
        cap_name = self.namingTemplates['variable'].format(unit=name, feature='capacity')
        values = capacity.get_value(debug=case.debug['enabled'])
        if isinstance(values, list):
          cap_val = 42 # placeholder
        else:
          cap_val = values
        mc.add_constant(cap_name, cap_val)
        # add component to applicable variable groups
        vg_capacities.add_variables(cap_name)
      elif capacity.type in ['StaticHistory', 'SyntheticHistory', 'Function', 'Variable']:
        # capacity is limited by a signal, so it has to be handled in the dispatch; don't include it here.
        # OR capacity is limited by a function, and we also can't handle it here, but in the dispatch.
        pass
      else:
        raise NotImplementedError(f'Capacity from "{capacity}" not implemented yet. Component: {cap_name}')

      for tracker in component.get_tracking_vars():
        resource_list = sorted(list(component.get_resources()))
        for resource in resource_list:
          var_name = self.namingTemplates['dispatch'].format(component=name, tracker=tracker, resource=resource)
          vg_init_disp.add_variables(var_name)
          vg_full_disp.add_variables(var_name)

  def _modify_econ_metrics(self, case: Case, components: list[Component]) -> None:
    """
      Modifies template to include economic metrics
      @ In, case, HERON Case, defining Case instance
      @ In, components, list[Component], case components
      @ Out, None
    """
    # get all economic metrics intended for use in TEAL and reported back
    econ_metrics = case.get_econ_metrics(nametype='output')
    tot_act_vars = self._get_activity_metrics(components)

    # find variable groups to update with economic metrics
    dispatch_out = self._template.find("VariableGroups/Group[@name='GRO_dispatch_out']")
    arma_samp_out = self._template.find("VariableGroups/Group[@name='GRO_armasamples_out_scalar']")
    # find point set output node to update with economic metrics
    arma_metrics = self._template.find("DataObjects/PointSet[@name='arma_metrics']")

    # update fields with econ metric names
    metrics = econ_metrics + tot_act_vars
    dispatch_out.add_variables(*metrics)
    arma_samp_out.add_variables(*metrics)
    arma_metrics.add_outputs(*metrics)

  def _add_uncertain_cashflow_params(self, components) -> None:
    cf_attrs = ["_driver", "_alpha", "_reference", "_scale"]

    vg_econ_uq = self._template.find("VariableGroups/Group[@name='GRO_econ_UQ']")
    mc = self._template.find("Samplers/MonteCarlo[@name='mc']")

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
        dist_snippet = snippet_factory.from_xml(dist_node)
        self._add_snippet(dist_snippet)  # added to Distributions

        # Add uncertain parameter to econ UQ variable group
        vg_econ_uq.add_variables(feat_name)

        # Add distribution to MonteCarlo sampler
        sampler_var = SamplerVariable(feat_name)
        sampler_var.set_distribution(dist_snippet)
        mc.add_variable(sampler_var)

  def _modify_inner_result_statistics(self, template, case, components):
    """
      Modifies template to include result statistics
      @ In, template, xml.etree.ElementTree.Element, root of XML to modify
      @ In, case, HERON Case, defining Case instance
      @ Out, None
    """
    # final return variable group (sent to outer)
    group_final_return = self._create_statistical_results_vargroup("GRO_final_return")

    # fill out PostProcessor nodes
    pp_node = template.find('Models').find(".//PostProcessor[@name='statistics']")
    # add default statistics
    result_statistics = case.get_result_statistics() # list of stats beyond default
    tot_act_vars = []
    for component in components:
      for tracker in component.get_tracking_vars():
        resource_list = np.sort(list(component.get_resources()))
        for resource in resource_list:
          tot_act_var = "TotalActivity"+ "__" +component.name + "__" + tracker + "__" + resource
          tot_act_vars.append(tot_act_var)
    for var in tot_act_vars:
      for stat, pref in zip(DEFAULT_STATS_NAMES, default_stats_prefixes):
        pp_node.append(xmlUtils.newNode(stat, text=var, attrib={'prefix': pref}))

    for em in econ_metrics + tot_act_vars:
      for stat, pref in zip(DEFAULT_STATS_NAMES, default_stats_prefixes):
        pp_node.append(xmlUtils.newNode(stat, text=em, attrib={'prefix': pref}))
      # add any user supplied statistics beyond defaults
      if any(stat not in DEFAULT_STATS_NAMES + default_stats_tot_act for stat in result_statistics):
        for raven_metric_name in result_statistics:
          if raven_metric_name not in DEFAULT_STATS_NAMES:
            prefix = self._get_stats_metrics_prefixes(case, [raven_metric_name], use_extra=False)[0]
            # add subnode to PostProcessor
            if raven_metric_name == 'percentile':
              # add percent attribute
              percent = result_statistics[raven_metric_name]
              if isinstance(percent, list):
                for p in percent:
                  pp_node.append(xmlUtils.newNode(raven_metric_name, text=em,
                                                  attrib={'prefix': prefix,
                                                          'percent': p}))
              else:

                pp_node.append(xmlUtils.newNode(raven_metric_name, text=em,
                                                attrib={'prefix': prefix,
                                                        'percent': percent}))
            elif raven_metric_name in ['valueAtRisk', 'expectedShortfall', 'sortinoRatio', 'gainLossRatio']:
              threshold = result_statistics[raven_metric_name]
              if isinstance(threshold, list):
                for t in threshold:
                  if not em.startswith("TotalActivity"):
                    pp_node.append(xmlUtils.newNode(raven_metric_name, text=em,
                                                  attrib={'prefix': prefix,
                                                          'threshold': t}))
              else:
                if not em.startswith("TotalActivity"):
                  pp_node.append(xmlUtils.newNode(raven_metric_name, text=em,
                                                attrib={'prefix': prefix,
                                                        'threshold': threshold}))
            else:
              if not em.startswith("TotalActivity"):
                pp_node.append(xmlUtils.newNode(raven_metric_name, text=em,
                                              attrib={'prefix': prefix}))
              if em.startswith("TotalActivity"):
                if prefix not in FINANCIAL_PREFIXES:
                  pp_node.append(xmlUtils.newNode(raven_metric_name, text=em,
                                              attrib={'prefix': prefix}))

      # if not specified, "sweep" mode has additional defaults
      elif case.get_mode() == 'sweep':
        sweep_stats_prefixes = self._get_stats_metrics_prefixes(case, SWEEP_DEFAULT_STATS_NAMES, use_extra=False)
        for em in econ_metrics:
          for stat, pref in zip(SWEEP_DEFAULT_STATS_NAMES, sweep_stats_prefixes):
            pp_node.append(xmlUtils.newNode(stat, text=em, attrib={'prefix': pref}))
        for var in tot_act_vars:
          for stat, pref in zip(SWEEP_DEFAULT_STATS_NAMES, sweep_stats_prefixes):
            pp_node.append(xmlUtils.newNode(stat, text=var, attrib={'prefix': pref}))
    # if not specified, "opt" mode is handled in _modify_inner_optimization_settings

  @staticmethod
  def _add_stats_to_postprocessor(pp, names, vars, meta) -> None:
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
