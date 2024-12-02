import sys
import os
import shutil

from .raven_template import RavenTemplate
from .snippets.files import File
from .snippets.models import Model, RavenCode, PostProcessor, EnsembleModel, ExternalModel
from .snippets.variablegroups import VariableGroup
from .snippets.dataobjects import DataSet, PointSet

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
    # TODO
    # disp_results_name = self.inner.get_dispatch_results_name()
    # self.outer.set_inner_data_name(disp_results_name, case.data_handling["inner_to_outer"])

  def writeWorkflow(self, destination, case, components, sources) -> None:
    self.outer.writeWorkflow(destination, case, components, sources)
    self.inner.writeWorkflow(destination, case, components, sources)

    # copy "write_inner.py", which has the denoising and capacity fixing algorithms
    write_inner_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
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
    inputs = []
    for file_node in self._template.findall("Files/Input"):
      file_node = File.from_xml(file_node)
      inputs.append(file_node)

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
    model = self.find("Models/Code[@subType='RAVEN']")
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
    # Use the existing model node to instantiate a RavenCode object. Using this instead of the existing XML provides
    # many utility functions for easier getting/setting of various attributes and subelement values.
    models = find_node(self._template, "Models")
    template_raven = models.find("Code[@subType='RAVEN']")
    if template_raven is None:
      raise ValueError("A RAVEN Code Entity must be specified in the 'outer' workflow template (bilevel_outer.xml) "
                       "for bilevel workflows, and none was found!")
    # Read existing XML into a RavenCode objects, then replace the existing node with the new object in the _template
    # XML tree. This lets us access the features of the RavenCode class while initializing from existing XML and
    # without creating a duplicate node.
    raven = RavenCode.from_xml(template_raven)
    models.remove(template_raven)
    self.add_snippet(raven)

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

  def createWorkflow(self, case, components, sources) ->  None:
    super().createWorkflow(case, components, sources)
    # FIXME Assume synthetic histories for now but could be multiple static histories

    # Parse expected nodes
    self._parse_all_of_class(parent=find_node(self._template, "VariableGroups"), cls=VariableGroup)

    # Parse the <Models> node of the template XML. We expect to see three models:
    #   1. An ExternalModel named "dispatch"
    #   2. An EnsembleModel named "sample_and_dispatch"
    #   3. A PostProcessor named "statistics"
    # NOTE: An error will be raised if any of these nodes are missing.
    dispatch_model, ensemble_model, postprocessor = self._parse_expected(
      parent=find_node(self._template, "Models"),
      expected_nodes=[
        {
          "tag": "ExternalModel",
          "class": ExternalModel,
          "name": "dispatch"
        },
        {
          "tag": "EnsembleModel",
          "class": EnsembleModel,
          "name": "sample_and_dispatch"
        },
        {
          "tag": "PostProcessor",
          "class": PostProcessor,
          "name": "statistics"
        }
    ])

    # Add models, steps, and their requisite data objects and outstreams for each case source
    for source in sources:
      if source.is_type("ARMA"):
        load_step = self._rom_load_step(source)
        rom = self._build_rom_from_source(source)  # TODO
        print_meta_step = self._rom_meta_print_step(rom)

        self._add_step_to_sequence(load_step, index=0)
        self._add_step_to_sequence(print_meta_step, index=-1)

        # Add ROM to ensemble. We need to create the input/output data objects for the ROM to do this.
        inp_name = self.namingTemplates['data object'].format(source=source.name, contents='placeholder')
        inp_do = PointSet(inp_name)
        inp_do.set_inputs("scaling")
        self.add_snippet(inp_do)

        eval_name = self.namingTemplates['data object'].format(source=source.name, contents='samples')
        eval_do = DataSet(eval_name)
        eval_do.set_inputs("scaling")
        out_vars = source.get_variable()
        eval_do.set_outputs(out_vars)
        eval_do.add_index(case.get_time_name(), out_vars)
        eval_do.add_index(case.get_year_name(), out_vars)
        self.add_snippet(eval_do)

        ens_sub = ensemble_model.add_model(rom)
        ens_sub.add_input(inp_do)
        ens_sub.set_target_evaluation(eval_do)

        # TODO: extra clustered eval mode settings
      elif source.is_type("CSV"):
        # Only need to change settings for debug mode
        pass
      elif source.is_type("Function"):
        # nothing to do ... ?
        pass

    # Modify variable groups to reflect case labels and time variable names
    self._case_labels(case.get_labels())
    self._time_vars(case.get_time_name(), case.get_year_name())

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
    case_name = case_name = self.namingTemplates['jobname'].format(case=case.name, io='i')
    run_info = super()._initialize_runinfo(case, case_name)

    # parallel settings
    if case.innerParallel:
      run_info.internal_parallel = True
      run_info.batch_size = case.innerParallel

  def _case_labels(self, case_labels: dict[str, str]) -> None:
    """
    Adds case labels to relevant variable groups
    @ In, case_labels, dict[str, str], the case labels
    @ Out, None
    """
    if not case_labels:
      return

    labels_group = VariableGroup("GRO_case_labels")
    labels_group.add_variable(*[f"{key}_label" for key in case_labels.keys()])
    self.add_snippet(labels_group)

    for vg in ["GRO_armasamples_in_scalar", "GRO_dispatch_in_scalar"]:
      group = self._template.find(f"VariableGroups/Group[@name='{vg}']")
      group.add_variable(labels_group.name)

  def _time_vars(self, time_name: str, year_name: str) -> None:
    """
    Update variable groups and data objects to have the correct time variable names.
    @ In, time_name, str, name of time variable
    @ In, year_name, str, name of year variable
    @ Out, None
    """
    for vg in ["GRO_dispatch", "GRO_full_dispatch_indices"]:
      group = self._template.find(f"VariableGroups/Group[@name='{vg}']")
      group.add_variable(time_name, year_name)

    for time_index in self._template.findall("DataObjects/DataSet/Index[@var='Time']"):
      time_index.set("var", time_name)

    for year_index in self._template.findall("DataObjects/DataSet/Index[@var='Year']"):
      year_index.set("var", year_name)
