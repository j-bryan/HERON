# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Drivers which translate HERON features to RAVEN workflow template changes. Add an option to HERON
  by creating a new FeatureDriver for that feature.

  @author: Jacob Bryan (@j-bryan)
  @date: 2024-11-08
"""
import os
import shutil
from abc import abstractmethod
import xml.etree.ElementTree as ET

from ..raven_templates import *


class FeatureDriver:
  """
  FeatureDrivers translate HERON features to RAVEN workflow template changes. This makes feature
  logic more portable across different templates.
  """
  def __init__(self, name: str):
    """
    Feature driver constructor

    @ In, name, str, name of the feature
    """
    self.name = name

  def edit_template(self, template, case, components, sources):
    """
    Edits the template in-place
    @ In, template
    @ In, case
    @ In, components
    @ In, sources
    """
    # The order of these functions is chosen based on which XML blocks reference others. Modifying the
    # XML in this order should allow for editing nodes based on changes to objects they reference, if needed.

    # NOTE: FeatureDrivers which make simple edits don't necessarily need to follow this pattern, but this
    #       provides a general framework for making edits to RAVEN workflows.

    # Group 1
    self._modify_files(template, case, components, sources)
    self._modify_databases(template, case, components, sources)
    self._modify_distributions(template, case, components, sources)
    self._modify_variablegroups(template, case, components, sources)
    # Group 2
    self._modify_dataobjects(template, case, components, sources)  # ref: VariableGroups
    # Group 3
    self._modify_outstreams(template, case, components, sources)  # ref: VariableGroups, DataObjects
    self._modify_models(template, case, components, sources)  # ref: DataObjects, other Models
    self._modify_samplers(template, case, components, sources)  # ref: Distributions, DataObjects
    # Group 4
    self._modify_optimizers(template, case, components, sources)  # ref: DataObjects, Models, Samplers
    # Group 5
    self._modify_steps(template, case, components, sources)  # ref: everything but VariableGroups and Distributions
    # Group 6
    self._modify_runinfo(template, case, components, sources)  # ref: Steps (step names)

    return template

  def _modify_files(self, template, case, components, sources):
    pass

  def _modify_databases(self, template, case, components, sources):
    pass

  def _modify_distributions(self, template, case, components, sources):
    pass

  def _modify_variablegroups(self, template, case, components, sources):
    pass

  def _modify_dataobjects(self, template, case, components, sources):
    pass

  def _modify_outstreams(self, template, case, components, sources):
    pass

  def _modify_models(self, template, case, components, sources):
    pass

  def _modify_samplers(self, template, case, components, sources):
    pass

  def _modify_optimizers(self, template, case, components, sources):
    pass

  def _modify_steps(self, template, case, components, sources):
    pass

  def _modify_runinfo(self, template, case, components, sources):
    pass

class FeatureCollection(FeatureDriver):
  """
  Groups FeatureDrivers together to define more complex features. Useful for grouping together
  features which are commonly used together, handling entity creation and entity settings
  separately, and more!
  """
  def __init__(self):
    self._features = []

  def edit_template(self, template, case, components, sources):
    for feature in self._features:
      feature.edit_template(template, case, components, sources)





def subelement(parent, tag, attrib={}, text="", **extra):
  new_element = ET.Element(tag, attrib, **extra)
  new_element.text = text
  parent.append(new_element)
