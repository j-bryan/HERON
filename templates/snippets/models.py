import xml.etree.ElementTree as ET

from ..xml_utils import find_node
from ..decorators import listproperty
from .base import RavenSnippet


class RavenCode(RavenSnippet):
  """
  Sets up a <Code> model to run inner RAVEN workflow.
  """
  tag = "Code"
  snippet_class = "Models"
  subtype = "RAVEN"

  def __init__(self, name: str | None = None):
    super().__init__(name)
    self._py_cmd = None

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

  @property
  def executable(self) -> str | None:
    node = self.find("executable")
    return None if node is None else node.text

  @executable.setter
  def executable(self, value: str) -> None:
    find_node(self, "executable").text = value

  @property
  def python_command(self) -> str | None:
    return self._py_cmd

  @python_command.setter
  def python_command(self, cmd: str) -> None:
    if self._py_cmd is None:
      ET.SubElement(self, "clargs", {"type": "prepend", "arg": cmd})
    else:
      node = self.find(f"clargs[@type='prepend' and @arg='{cmd}']")
      node.set("arg", cmd)
    self._py_cmd = cmd

class GaussianProcessRegressor(RavenSnippet):
  tag = "ROM"
  snippet_class = "Models"
  subtype = "GaussianProcessRegressor"

  def __init__(self, name: str | None = None):
    # FIXME: Only custom_kernel setting exposed to HERON input
    default_settings = {
      "alpha": 1e-8,
      "n_restarts_optimizer": 5,
      "normalize_y": True,
      "kernel": "Custom",
      "custom_kernel": "(Constant*Matern)",
      "anisotropic": True,
      "multioutput": False
    }
    super().__init__(name, default_settings)

  @listproperty
  def features(self) -> list[str]:
    node = self.find("Features")
    return getattr(node, "text", []) or []

  @features.setter
  def features(self, value: list[str]) -> None:
    find_node(self, "Features").text = value

  @property
  def target(self) -> str:
    node = self.find("Target")
    return None if node is None else node.text

  @target.setter
  def target(self, value: str) -> None:
    find_node(self, "Target").text = value

  @property
  def custom_kernel(self) -> str:
    node = self.find("custom_kernel")
    return node.text

  @custom_kernel.setter
  def custom_kernel(self, value: str) -> None:
    self.find("custom_kernel").text = value

class EnsembleModel(RavenSnippet):
  tag = "EnsembleModel"
  snippet_class = "Models"
  subtype = ""

class EconomicRatioPostProcessor(RavenSnippet):
  tag = "PostProcessor"
  snippet_class = "Models"
  subtype = "EconomicRatio"

  def add_statistic(self, tag: str, prefix: str, variable: str, **kwargs) -> None:
    # NOTE: This allows duplicate nodes to be added. It's good to avoid that but won't cause anything to crash.
    ET.SubElement(self, tag, prefix=prefix, **kwargs).text = variable

class ExternalModel(RavenSnippet):
  tag = "ExternalModel"
  snippet_class = "Models"
  subtype = ""

  @classmethod
  def from_xml(cls, node: ET.Element) -> "ExternalModel":
    model = cls()
    model.attrib |= node.attrib
    for sub in node:
      if sub.tag == "variables":
        model.variables = [v.strip() for v in sub.text.split(",")]
      else:
        model.append(sub)
    return model

  @listproperty
  def variables(self) -> list[str]:
    vars_node = self.find("variables")
    return [] if vars_node is None or not vars_node.text else vars_node.text

  @variables.setter
  def variables(self, value: list[str]) -> None:
    vars_node = find_node(self, "variables")
    vars_node.text = value

class HeronDispatchModel(ExternalModel):
  snippet_class = "Models"
  subtype = "HERON.DispatchManager"

class PickledROM(RavenSnippet):
  tag = "ROM"
  snippet_class = "Models"
  subtype = "pickledROM"
