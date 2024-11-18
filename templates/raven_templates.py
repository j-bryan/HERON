# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  RAVEN workflow templates

  @author: j-bryan
  @date: 2024-10-29
"""
import sys
import os
import xml.etree.ElementTree as ET

from .feature_drivers import FeatureDriver

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from HERON.src.base import Base
from HERON.src.Cases import Case
from HERON.src.Components import Component
from HERON.src.Placeholders import ARMA, CSV
import HERON.src._utils as hutils
sys.path.pop()

RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))

sys.path.append(os.path.join(RAVEN_LOC, '..'))
from ravenframework.InputTemplates.TemplateBaseClass import Template
sys.path.pop()


class RavenTemplate(Template):
  """ Template class for RAVEN workflows """
  Template.addNamingTemplates({'jobname'        : '{case}_{io}',
                               'stepname'       : '{action}_{subject}',
                               'variable'       : '{unit}_{feature}',
                               'dispatch'       : 'Dispatch__{component}__{tracker}__{resource}',
                               'tot_activity'   :'{stats}_TotalActivity__{component}__{tracker}__{resource}',
                               'data object'    : '{source}_{contents}',
                               'distribution'   : '{unit}_{feature}_dist',
                               'ARMA sampler'   : '{rom}_sampler',
                               'lib file'       : 'heron.lib', # TODO use case name?
                               'cashfname'      : '_{component}{cashname}',
                               're_cash'        : '_rec_{period}_{driverType}{driverName}',
                               'cluster_index'  : '_ROM_Cluster',
                               'metric_name'    : '{stats}_{econ}',
                               })

  def __init__(self):
    super().__init__()
    self.features = []

  ######################
  # RAVEN Template API #
  ######################
  def loadTemplate(self):
    # TODO
    # load XML from file
    pass

  def createWorkflow(self, case: Case, components: list[Component], sources: list[CSV | ARMA]):
    """
    Create workflow by applying feature changes to the template XML

    @ In, case, HERON.src.Cases.Case
    @ In, components, list[HERON.src.Components.Component]
    @ In, sources, TODO
    @ Out, None
    """
    for feature in self.features:
      feature.edit_template(self._template, case, components, sources)
    return self

  def writeWorkflow(self):
    # TODO
    pass

  ############################
  # XML manipulation methods #
  ############################
  def find(self, match: str, namespaces: str = None) -> ET.Element | None:
    """
    Find the first node with a matching tag or path in the template XML. Wraps the
    xml.etree.ElementTree.Element.find() method.

    @ In, match, str, string to match tag name or path
    @ In, namespaces, str, optional, an optional mapping form namespace prefix to full name
    @ Out, node, ET.Element | None, first element with matching tag or None if no matches are found
    """
    return self._template.find(match, namespaces)

  def findall(self, match: str, namespaces: str = None) -> list[ET.Element] | None:
    """
    Find all nodes  with a matching tag or path in the template XML. Wraps the
    xml.etree.ElementTree.Element.findall() method.

    @ In, match, str, string to match tag name or path
    @ In, namespaces, str, optional, an optional mapping form namespace prefix to full name
    @ Out, nodes, list[ET.Element] | None, first element with matching tag or None if no matches are found
    """
    return self._template.findall(match, namespaces)

  ################################
  # Feature modification methods #
  ################################
  def add_features(self, *feats: FeatureDriver):
    """
    Add features to the template XML

    @ In, feats, FeatureDriver, one or more features to add to the template XML
    @ Out, None
    """
    self.features.extend(feats)

# Templates for specific workflow types
class FlatOneHistoryTemplate(Template):
  Template.addNamingTemplates({"model_name": "dispatch"})


class FlatFixedCapacitiesTemplate(Template):
  Template.addNamingTemplates({"model_name": "dispatch"})


class BilevelOuterTemplate(Template):
  Template.addNamingTemplates({"model_name": "raven",
                               "sampler_name": "sampler",
                               "optimize_namer": "opt"})


class BilevelInnerTemplate(Template):
  Template.addNamingTemplates({"model_name": "dispatch",
                               "sampler_name": "sampler"})
