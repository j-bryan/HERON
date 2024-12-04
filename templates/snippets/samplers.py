"""
Sampler features

@author: Jacob Bryan (@j-bryan)
@date: 2024-11-08
"""
from typing import Any
import xml.etree.ElementTree as ET

from ..utils import _to_string

from ..utils import find_node
from .base import RavenSnippet, node_property
from .distributions import Distribution


# FIXME: The <variable> node in a sampler accepts different children depending on the sampler type. Perhaps it would be
#        better to defer this capability to the sampler classes?
class SampledVariable(RavenSnippet):
  tag = "variable"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    node_property(cls, "initial")
    node_property(cls, "distribution")

  def __init__(self, name: str) -> None:
    super().__init__(name)

  def set_sampling_strategy(self, construction="equal", type="CDF", steps: int | None = None, values: list[float] = [0, 1]) -> None:
    if type == "CDF" and not all([0 <= val <= 1 for val in values]):
      raise ValueError(f"All CDF values must lie on the interval [0, 1]. Values received: {values}.")

    grid_node = find_node(self, "grid")
    grid_node.set("construction", construction)
    grid_node.set("type", type)
    if construction == "equal":
      grid_node.set("steps", steps)
    grid_node.text = _to_string(values, delimiter=" ")  # Direct call to _to_string to use space-delimited list join


class Sampler(RavenSnippet):
  snippet_class = "Samplers"

  def __init__(self, name: str) -> None:
    super().__init__(name)
    # TODO: samplerInit node?
    self._num_sampled_vars = 0

  @property
  def num_sampled_vars(self) -> int:
    return self._num_sampled_vars

  def add_variable(self, variable: SampledVariable) -> None:
    self.append(variable)
    self._num_sampled_vars += 1

  def add_constant(self, name: str, value: str) -> None:
    constant = ET.SubElement(self, "constant", attrib={"name": name})
    constant.text = _to_string(value)


class Grid(Sampler):
  tag = "Grid"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    node_property(cls, "denoises", "constant[@name='denoises']")

  def __init__(self, name: str):
    super().__init__("Grid", name)
    # Grid sampler denoises defaults to 1
    # FIXME: Do ALL Grid samplers need the denoises variable?
    self.denoises = 1

  def add_variable(self, variable: SampledVariable):
    pass

class MonteCarlo(Sampler):
  tag = "MonteCarlo"

class Stratified(Sampler):
  tag = "Stratified"

class CustomSampler(Sampler):
  tag = "CustomSampler"
