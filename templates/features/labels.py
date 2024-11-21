import xml.etree.ElementTree as ET
from .feature_driver import FeatureDriver


# TODO: does it make sense to add this way?
class CaseLabels(FeatureDriver):
  """
  Add case labels to sampler/optimizer node,
  """
  def _modify_variablegroups(self, template, case, components, sources):
    vargroups = template.find("VariableGroups")
    gro_case_labels = ET.SubElement(vargroups, "Group", attrib={"name": "GRO_case_labels"})
    gro_case_labels.text = ', '.join([f'{key}_label' for key in case.get_labels().keys()])

  def _modify_models(self, template, case, components, sources):
    pass

  def _modify_samplers(self, template, case, components, sources):
    for key, value in case.get_labels().items():
      var_name = self.namingTemplates['variable'].format(unit=key, feature='label')
      samps_node.append(xmlUtils.newNode('constant', text=value, attrib={'name': var_name}))
