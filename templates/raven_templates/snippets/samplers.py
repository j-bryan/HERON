"""
Sampler features

@author: Jacob Bryan (@j-bryan)
@date: 2024-11-08
"""
from typing import Any
import xml.etree.ElementTree as ET

from ..xml_utils import _to_string

from ..xml_utils import find_node
from .base import RavenSnippet
from .distributions import Distribution


# FIXME: The <variable> node in a sampler accepts different children depending on the sampler type. Perhaps it would be
#        better to defer this capability to the sampler classes?
class SamplerVariable(RavenSnippet):
  def __init__(self, name: str) -> None:
    super().__init__("variable", name)

  def set_distribution(self, distribution: Distribution) -> None:
    """
    Set the reference to the distribution used to sample this variable
    @ In, distribution, Distribution, the distribution of the variable
    @ Out, None
    """
    dist_node = find_node(self, "distribution")
    dist_node.text = distribution.name

  def set_sampling_strategy(self, construction="equal", type="CDF", steps: int | None = None, values: list[float] = [0, 1]) -> None:
    if type == "CDF" and not all([0 <= val <= 1 for val in values]):
      raise ValueError(f"All CDF values must lie on the interval [0, 1]. Values received: {values}.")

    grid_node = find_node(self, "grid")
    grid_node.set("construction", construction)
    grid_node.set("type", type)
    if construction == "equal":
      grid_node.set("steps", steps)
    grid_node.text = _to_string(values, delimiter=" ")  # Direct call to _to_string to use space-delimited list join

  def set_initial(self, value: float) -> None:
    initial = find_node(self, "initial")
    initial.text = _to_string(value)

class Sampler(RavenSnippet):
  def __init__(self, tag: str, name: str) -> None:
    super().__init__(tag, name, class_name="Samplers")
    # TODO: samplerInit node?
    self._num_sampled_vars = 0

  def get_num_sampled_vars(self) -> int:
    return self._num_sampled_vars

  def add_variable(self, variable: SamplerVariable) -> None:
    self.append(variable)
    self._num_sampled_vars += 1

  def add_constant(self, name: str, value: str) -> None:
    constant = ET.SubElement(self, "constant", attrib={"name": name})
    constant.text = _to_string(value)

class GridSampler(Sampler):
  def __init__(self, name: str):
    super().__init__("Grid", name)
    # Grid sampler denoises defaults to 1
    # FIXME: Do ALL Grid samplers need the denoises variable?
    self.add_constant(name="denoises", value=1)

  def add_variable(self, variable: SamplerVariable):
    pass

class MonteCarloSampler(Sampler):
  def __init__(self, name: str) -> None:
    super().__init__("MonteCarlo", name)

class StratifiedSampler(Sampler):
  def __init__(self, name: str) -> None:
    super().__init__("Stratified", name)

class CustomSampler(Sampler):
  def __init__(self, name: str) -> None:
    super().__init__("CustomSampler", name)
