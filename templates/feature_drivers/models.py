import os
import sys
import shutil
import xml.etree.ElementTree as ET

from .feature_driver import FeatureDriver
from .snippets import EntityNode
from .utils import build_opt_metric_from_name, get_feature_list, get_subelement

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
sys.path.pop()

# get raven location
RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))


class RavenCode(FeatureDriver):
  """
  Sets up a <Code> model to run inner RAVEN workflow.
  """
  def _modify_models(self, template, case, components, sources):
    # We require the template to already define a <Code> node for the inner RAVEN run, which we modify here.
    # TODO:
    raven = template.find("Models/Code[@subType='RAVEN']")
    if not raven:
      models = template.find("Models")
      raise ValueError(f"No <Code> node found in the template XML! Children of <Models> node found: {[child.tag for child in models]}")

    # Where is the RAVEN executable?
    executable = raven.find("executable")  # NOTE: returns None if node not found
    if not executable:  # make node if not found
      executable = ET.SubElement(raven, "executable")
    raven_exec_guess = os.path.abspath(os.path.join(RAVEN_LOC, "..", "raven_framework"))
    if os.path.exists(raven_exec_guess):
      executable.text = raven_exec_guess
    elif shutil.which("raven_framework") is not None:
      executable.text = "raven_framework"
    else:
      raise RuntimeError("raven_framework not in PATH and not at "+raven_exec_guess)

    # custom python command for running raven (for example, "coverage run")
    if cmd := case.get_py_cmd_for_raven():
      attribs = {"type": "prepend", "arg": cmd}
      new = ET.Element("clargs", attrib=attribs)
      raven.append(new)

    # conversion script
    conv = raven.find("conversion")
    if conv is None:
      conv = ET.SubElement(raven, "conversion")
    conv_inp = conv.find("input")
    if conv_inp is None:
      conv_inp = ET.SubElement(conv, "input")
    conv_inp.attrib["source"] = "../write_inner.py"

    # Add variable aliases for Inner
    alias_template = "Samplers|MonteCarlo@name:mc_arma_dispatch|constant@name:{}"
    for component in components:
      attribs = {"variable": f"{component.name}_capacity", "type": "input"}
      alias = ET.SubElement(raven, "alias", attribs)
      alias.text = alias_template.format(component.name + "_capacity")

    # Add label aliases placed inside models
    for label in case.get_labels():
      attribs = {'variable': f'{label}_label', 'type':'input'}
      label_alias = ET.SubElement(raven, "alias", attrib=attribs)
      label_alias.text = alias_template.format(label + "_label")

    # data handling: inner to outer data format
    output_tags = {"netcdf": "outputDatabase",
                   "csv": "outputExportOutStreams"}
    output_node = ET.SubElement(raven, output_tags.get(case.data_handling["inner_to_outer"]))
    output_node.text = "disp_results"

  def _modify_databases(self, template, case, components, sources):
    if case.data_handling["inner_to_outer"] == "netcdf":
      databases = template.find("Databases")
      disp_results = ET.SubElement(databases, "")

class InnerDataHandling(FeatureDriver):
  def __init__(self, model_name: str):
    super().__init__("")  # no name for this feature itself
    self._model_name = model_name

  def edit_template(self, template, case, components, sources):
    # inner to outer data format
    if case.data_handling["inner_to_outer"] == "netcdf":
      self._database_handling(template, case, components, sources)
    elif case.data_handling["inner_to_outer"] == "csv":
      self._csv_handling(template, case, components, sources)
    else:
      raise ValueError(f"Unrecognized inner to outer data handling type '{case.data_handling['inner_to_outer']}'")

  # def _modify_models(self, template, case, components, sources):
  #   # inner to outer data format
  #   output_tag = "outputExportOutStreams" if case.data_handling["inner_to_outer"] == "csv" else "outputDatabase"
  #   output_node = ET.SubElement(raven, output_tag)
  #   output_node.text = "disp_results"

  def _database_handling(self, template, case, components, sources):
    output_tag = "outputExportOutStreams"

class GaussianProcessRegressor(FeatureDriver):
  def __init__(self):
    super().__init__()
    self._name = "gpROM"

  def _modify_models(self, template, case, components, sources):
    features = get_feature_list(case, components)
    # TODO: Move default values to somewhere they could actually be reached,
    #       like somewhere in the case input specs.
    model_params = {
      "Features": ", ".join(features),
      "Target": build_opt_metric_from_name(case),
      "alpha": 1e-8,
      "n_restarts_optimizer": 5,
      "normalize_y": True,
      "kernel": "Custom",
      "custom_kernel": "(Constant*Matern)",
      "anisotropic": True,
      "multioutput": False
    }
    rom = EntityNode("ROM", "gpROM", "GaussianProcessRegressor", kwarg_subs=model_params)

    # Add to Models node
    models = template.find("Models")
    models.append(rom)


class EnsembleModel(FeatureDriver):
  pass
