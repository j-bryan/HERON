from typing import Any
import os
import sys
import shutil
import xml.etree.ElementTree as ET

from .base import Feature, Entity, FeatureCollection
from .snippets import AssemblerNode
from .databases import Database
from .utils import build_opt_metric_from_name, get_feature_list, get_subelement

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
sys.path.pop()

# get raven location
RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))


class Model(Feature, Entity):
  def __init__(self, name: str, type_name: str, subtype_name: str = "", settings: dict[str, Any] = {}):
    super().__init__(name, "Models", type_name, subtype_name, settings)

  def get_inputs(self) -> list[Entity]:
    return []

  def get_outputs(self) -> list[Entity]:
    return []


class ModelSettings(Feature):
  pass


class RavenCodeSettings(Feature):
  """
  Sets setting values for a slave RAVEN instance. Must be paired with a template which already has a
  <Code subType='RAVEN'> model.
  """
  def edit_template(self, template, case, components, sources):
    raven = template.find("Models/Code[@subType='RAVEN']")
    if not raven:
      raise ValueError("A <Code> block for to run RAVEN has not been found! A template which includes this block must "
                       "be used with this RavenCodeSettings feature class.")

  def get_model_name(self, template):
    raven = template.find("Models/Code[@subType='RAVEN']")
    raven_name = raven.attrib["name"]
    return raven_name

  @staticmethod
  def _find_raven_executable():
    exec_path = os.path.abspath(os.path.join(RAVEN_LOC, "..", "raven_framework"))
    if os.path.exists(executable):
      executable = exec_path
    elif shutil.which("raven_ravemework" is not None):
      executable = "raven_framework"
    else:
      raise RuntimeError(f"raven_framework not in PATH and not at {exec_path}")
    return executable


class RavenCode(Feature, Entity):
  """
  Sets up a <Code> model to run inner RAVEN workflow.
  """
  def __init__(self, name: str):
    super().__init__(name=name, class_name="Model", type_name="Code", subtype_name="RAVEN")

  def edit_template(self, template, case, components, sources):
    # Find or make the main Models node
    models = template.find("Models")

    # Only the RAVEN executable location is a simple key-value pair setting
    # Where is the RAVEN executable?
    executable = self._find_raven_executable()
    settings = {"executable": executable}

    # Add settings and convert to XML
    self.add_settings(settings)
    raven = self.to_xml()
    models.append(raven)

    # custom python command for running raven (for example, "coverage run")
    if cmd := case.get_py_cmd_for_raven():
      attribs = {"type": "prepend", "arg": cmd}
      clargs = ET.Element("clargs", attrib=attribs)
      raven.append(clargs)

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
    output_target = "disp_results"  # TODO: expose to set from outside this class
    data_handling = case.data_handling["inner_to_outer"]
    output_node = ET.SubElement(raven, output_tags.get(data_handling))
    output_node.text = output_target

  @staticmethod
  def _find_raven_executable():
    exec_path = os.path.abspath(os.path.join(RAVEN_LOC, "..", "raven_framework"))
    if os.path.exists(executable):
      executable = exec_path
    elif shutil.which("raven_ravemework" is not None):
      executable = "raven_framework"
    else:
      raise RuntimeError(f"raven_framework not in PATH and not at {exec_path}")
    return executable

class DispatchDataHandling(Feature):
  """  """
  def __init__(self, name: str):
    self._name = name

  def edit_template(self, template, case, components, sources):
    # Create appropriate Database or DataObject depending on selected handling
    data_handling = case.data_handling["inner_to_outer"]
    if data_handling == "netcdf":  # Make a NetCDF database
      self._handle_with_database(template, case)
    elif data_handling == "csv":  # Make a PointSet or HistorySet and an OutStream which directs that DataObject to CSV
      self._handle_with_csv(template, case)
    else:
      raise ValueError(f"Inner data handling must use one of ['netcdf', 'csv']. Received {data_handling}.")

  def _handle_with_database(self, template, case):
    databases = template.find("Databases")

    if databases.find(f"NetCDF[@name={self._name}]"):  # Is the required database already in the XML?
      return

    database = Database(self._name, type_name="NetCDF", read_mode="overwrite")
    databases.append(database.to_xml())

  def _handle_with_csv(self, template, case):
    data_objects = template.find("DataObjects")
    # if data_objects.find(f"PointSet[@name={self._name}]") or data_objects.find(f"HistorySet[@name={self._name}]"):
    outstreams = template.find("OutStreams")


class GaussianProcessRegressor(Feature, Entity):
  def __init__(self, name: str, settings: dict[str, Any] = {}):
    default_settings = {
      "Features": "",  # needs case & component info to populate
      "Target": "",    # needs case & component info to populate
      "alpha": 1e-8,
      "n_restarts_optimizer": 5,
      "normalize_y": True,
      "kernel": "Custom",
      "custom_kernel": "(Constant*Matern)",
      "anisotropic": True,
      "multioutput": False
    }
    super().__init__(name, "Models", "ROM" "GaussianProcessRegressor", default_settings)
    self.add_settings(settings)  # overwrites default settings if other values provided in constructor

  def edit_template(self, template, case, components, sources):
    features = get_feature_list(case, components)
    # Set case-dependent model paramters
    model_params = {
      "Features": features,  # will be joined as comma separated list
      "Target": build_opt_metric_from_name(case)
    }
    self.add_settings(model_params)
    rom = self.to_xml()

    # Add to Models node
    models = template.find("Models")
    models.append(rom)


class EnsembleModel(Feature, Entity):
  def __init__(self, name: str, *models: Model):
    super().__init__(name, "Models", "EnsembleModel")
    self.models = models

  def to_xml(self):
    # Make EnsembleModel entity node
    ensemble_model = super().to_xml()

    # The models are added as child Assembler nodes
    for model in self.models:
      model_node = AssemblerNode.from_entity("Model", model)

  def edit_template(self, template, case, components, sources) -> None:
    pass
