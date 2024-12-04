from typing import Any
import os
import sys
import shutil
import xml.etree.ElementTree as ET

from .base import RavenSnippet, node_property, attrib_property
from .dataobjects import DataObject
from .databases import Database

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
sys.path.pop()

# get raven location
RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))


class Model(RavenSnippet):
  snippet_class = "Models"

  def __init__(self, name: str, settings: dict[str, Any] = {}):
    super().__init__(name, subelements=settings)

class RavenCode(Model):
  """
  Sets up a <Code> model to run inner RAVEN workflow.
  """
  tag = "Code"
  subtype = "RAVEN"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    node_property(cls, "executable")

  def __init__(self, name: str):
    super().__init__(name)
    self._set_executable()

  def _set_executable(self, path: str | None = None) -> None:
    exec_path = path or os.path.abspath(os.path.join(RAVEN_LOC, "..", "raven_framework"))
    if os.path.exists(exec_path):
      executable = exec_path
    elif shutil.which("raven_ravemework" is not None):
      executable = "raven_framework"
    else:
      raise RuntimeError(f"raven_framework not in PATH and not at {exec_path}")
    self.executable = executable

  def set_py_cmd(self, cmd: str) -> None:
    """
    Set custom python command for running raven
    @ In, cmd, str, prepended command
    @ Out, None
    """
    clargs = ET.Element("clargs", {"type": "prepend", "arg": cmd})
    self.append(clargs)

  def add_alias(self, name: str, suffix: str) -> None:
    alias_text = f"Samplers|MonteCarlo@name:mc_arma_dispatch|constant@name:{name}_{suffix}"  # TODO allow other samplers?
    alias = ET.SubElement(self, "alias", {"variable": f"{name}_{suffix}", "type": "input"})
    alias.text = alias_text

  def set_inner_data_handling(self, dest: str, dest_type: str) -> None:
    """
    Set the inner-to-outer data handling source object.
    @ In, dest, PrintOutStream | Database, the data handling object; may be either a CSV Print OutStream or a NetCDF4 Database
    @ Out, None
    """
    if dest_type == "csv":
      remove_tag = "outputDatabase"
      keep_tag = "outputExportOutStreams"
    elif dest_type == "netcdf":
      remove_tag = "outputExportOutStreams"
      keep_tag = "outputDatabase"
    else:
      raise ValueError(f"Model output export destination must be a CSV <Print> OutStream or a NetCDF Database. Received: {type(dest)}")

    if (remove_node := self.find(remove_tag)) is not None:
      self.remove(remove_node)

    keep_node = self.find(keep_tag)
    if keep_node is None:
      keep_node = ET.SubElement(self, keep_tag)
    keep_node.text = dest

class GaussianProcessRegressor(Model):
  tag = "ROM"
  subtype = "GaussianProcessRegressor"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    node_property(cls, "features", "Features")
    node_property(cls, "target", "Target")
    node_property(cls, "kernel", "custom_kernel")

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

  def __init__(self, name: str):
    # FIXME: Only custom_kernel setting exposed to HERON input
    super().__init__(name, self.default_settings)
    self._features = []

  def add_feature(self, feature: str):
    self._features.append(feature)
    self.features = self._features

class EnsembleModel(Model):
  tag = "EnsembleModel"
  subtype = ""

class EconomicRatioPostProcessor(Model):
  tag = "PostProcessor"
  subtype = "EconomicRatio"

  def add_statistic(self, tag: str, prefix: str, variable: str, **kwargs) -> None:
    ET.SubElement(self, tag, prefix=prefix, **kwargs).text = variable

class ExternalModel(Model):
  tag = "ExternalModel"
  subtype = ""

  def __init__(self, name: str) -> None:
    super().__init__(name)
    self._variables = []  # list[str]

  def add_variable(self, *vars: str) -> None:
    self._variables.extend(vars)
    self.text = self._variables

class PickledROM(Model):
  tag = "ROM"
  subtype = "pickledROM"
