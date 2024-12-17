"""
Sampler features

@author: Jacob Bryan (@j-bryan)
@date: 2024-11-08
"""
import xml.etree.ElementTree as ET

from ..xml_utils import find_node
from .base import RavenSnippet
from .distributions import Distribution


# FIXME: The <variable> node in a sampler accepts different children depending on the sampler type. Perhaps it would be
#        better to defer this capability to the sampler classes?
class SampledVariable(RavenSnippet):
  tag = "variable"

  def use_grid(self, type: str, construction: str, values: list[float], steps: int | None = None) -> None:
    attrib = {"type": type, "construction": construction}
    if steps:
      attrib["steps"] = steps
    ET.SubElement(self, "grid", attrib).text = " ".join([str(v) for v in values])

  @property
  def initial(self) -> float | None:
    node = self.find("initial")
    return None if node is None else node.text

  @initial.setter
  def initial(self, value: float) -> None:
    find_node(self, "initial").text = value

  @property
  def distribution(self) -> str:
    node = self.find("distribution")
    return None if node is None else node.text

  @distribution.setter
  def distribution(self, value: Distribution) -> None:
    find_node(self, "distribution").text = str(value)


class Sampler(RavenSnippet):
  snippet_class = "Samplers"

  @property
  def num_sampled_vars(self) -> int:
    return len(self.findall("variable"))

  @property
  def denoises(self) -> int | None:
    node = self.find("constant[@name='denoises']")
    return None if node is None else node.text

  @denoises.setter
  def denoises(self, value: int) -> None:
    find_node(self, "constant[@name='denoises']").text = value

  @property
  def init_seed(self) -> int | None:
    node = self.find("samplerInit/initialSeed")
    return None if node is None else node.text

  @init_seed.setter
  def init_seed(self, value: int) -> None:
    find_node(self, "samplerInit/initialSeed").text = value

  @property
  def init_limit(self) -> int | None:
    node = self.find("samplerInit/limit")
    return None if node is None else node.text

  @init_limit.setter
  def init_limit(self, value: int) -> None:
    find_node(self, "samplerInit/limit").text = value

  def add_variable(self, variable: SampledVariable) -> None:
    self.append(variable)

  def add_constant(self, name: str, value: str) -> None:
    ET.SubElement(self, "constant", attrib={"name": name}).text = value

  def has_variable(self, variable: str | SampledVariable) -> bool:
    """
    Does the sampler sample a given variable?
    @ In, variable, str | SampledVariable, the variable to check for
    @ Out, var_found, bool, if the variable is in the sampler
    """
    var_name = variable if isinstance(variable, str) else variable.name
    var_found = self.find(f"variable[@name='{var_name}']") is not None
    return var_found

class Grid(Sampler):
  tag = "Grid"

class MonteCarlo(Sampler):
  tag = "MonteCarlo"

class Stratified(Sampler):
  tag = "Stratified"

  def __init__(self, name: str | None = None, settings: dict = {}) -> None:
    super().__init__(name, settings)
    # Must have samplerInit node
    ET.SubElement(self, "samplerInit")

class CustomSampler(Sampler):
  tag = "CustomSampler"

class EnsembleForward(Sampler):
  tag = "EnsembleForward"
  sampler_types = {samp_type.tag: samp_type for samp_type in [Grid, MonteCarlo, Stratified, CustomSampler]}

  @classmethod
  def from_xml(cls, node: ET.Element) -> "EnsembleForward":
    # The EnsembleForward sampler takes other samplers as subelements, so here we take care to create the
    # appropriate Sampler objects for these subnodes if they're of an implemented type.
    sampler = cls()
    sampler.attrib |= node.attrib
    for sub in node:
      if sub.tag in cls.sampler_types:
        sampler.append(cls.sampler_types[sub.tag].from_xml(sub))
      else:
        sampler.append(sub)
    return sampler
