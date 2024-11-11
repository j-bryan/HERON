"""
Sampler features

@author: Jacob Bryan (@j-bryan)
@date: 2024-11-08
"""
import xml.etree.ElementTree as ET

from .feature_driver import FeatureDriver, FeatureCollection
from .naming_templates import NAMING_TEMPLATES
from .snippets import EntityNode


class Sampler(FeatureDriver):
  def _modify_distributions(self, template, case, components, sources):
    pass


class GridSampler(FeatureDriver):
  def _modify_samplers(self, template, case, components, sources):
    grid = ET.Element("Grid", attrib={"name": "grid"})
    # TODO: Move "denoises" node to something for SyntheticHistories?
    denoises = ET.SubElement(grid, "constant", attrib={"name": "denoises"})
    denoises.text = case.get_num_samples()

    # add "GRO_case_labels" to sampler input if case has labels
    # TODO: refactor to be handled for all applicable samplers and optimizers
    for key, value in case.get_labels().items():
      label_name = NAMING_TEMPLATES['variable'].format(unit=key, feature='label')
      node = ET.Element(grid, "constant", attrib={"name": label_name})
      node.text = value

    # TODO: this is modifying distributions
    for key, value in case.dispatch_vars.items():
      var_name = self.namingTemplates['variable'].format(unit=key, feature='dispatch')
      vals = value.get_value(debug=case.debug['enabled'])
      if isinstance(vals, list):
        dist, xml = self._create_new_sweep_capacity(key, var_name, vals, sampler)
        dists_node.append(dist)
        grid.append(xml)

class MonteCarloSampler(FeatureDriver):
  pass

class StratifiedSampler(FeatureDriver):
  pass

class CustomSampler(FeatureDriver):
  def __init__(self, name: str):
    super().__init__()
    self._name = "sampler"

  def _modify_samplers(self, template, case, components, sources):
    sampler = EntityNode("CustomSampler", self._name)
    # TODO
