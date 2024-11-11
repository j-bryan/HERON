import os
import sys
import shutil
import xml.etree.ElementTree as ET

from .feature_driver import FeatureDriver
from .snippets import EntityNode
from .utils import build_opt_metric_from_name, get_feature_list

# load utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
sys.path.pop()

# get raven location
RAVEN_LOC = os.path.abspath(os.path.join(hutils.get_raven_loc(), "ravenframework"))


class RavenCodeModel(FeatureDriver):
  """
  Sets up a <Code> model to run inner RAVEN workflow
  """
  def _modify_models(self, template, case, components, sources):
    raven = template.find(".//Models/Code[@subType='RAVEN']")
    raven_exec = raven.find('executable')
    raven_exec_guess = os.path.abspath(os.path.join(RAVEN_LOC, '..', 'raven_framework'))
    if os.path.exists(raven_exec_guess):
      raven_exec.text = raven_exec_guess
    elif shutil.which("raven_framework") is not None:
      raven_exec.text = "raven_framework"
    else:
      raise RuntimeError("raven_framework not in PATH and not at "+raven_exec_guess)
    # custom python command for running raven (for example, "coverage run")
    if case.get_py_cmd_for_raven() is not None:
      attribs = {'type': 'prepend', 'arg': case.get_py_cmd_for_raven()}
      new = ET.Element('clargs', attrib=attribs)
      raven.append(new)
    # conversion script
    conv = raven.find('conversion').find('input')
    conv.attrib['source'] = '../write_inner.py'

    # Set variable aliases for Inner
    alias_template = 'Samplers|MonteCarlo@name:mc_arma_dispatch|constant@name:{}'
    for component in components:
      name = component.name
      attribs = {"variable": f"{name}_capacity", "type": "input"}
      alias = ET.Element("alias", attribs)
      alias.text = alias_template.format()
      raven.append(alias)

    # # label aliases placed inside models
    # for label in case.get_labels():
    #   attribs = {'variable': f'{label}_label', 'type':'input'}
    #   new = xmlUtils.newNode('alias', text=text.format(label + '_label'), attrib=attribs)
    #   raven.append(new)

    # # data handling: inner to outer data format
    # if case.data_handling['inner_to_outer'] == 'csv':
    #   # swap the outputDatabase to outputExportOutStreams
    #   output_node = template.find('Models').find('Code').find('outputDatabase')
    #   output_node.tag = 'outputExportOutStreams'
    #   # no need to change name, as database and outstream have the same name


class InnerDataHandling(FeatureDriver):
  def _modify_models(self, template, case, components, sources):
    # label aliases placed inside models
    for label in case.get_labels():
      attribs = {'variable': f'{label}_label', 'type':'input'}
      new = xmlUtils.newNode('alias', text=text.format(label + '_label'), attrib=attribs)
      raven.append(new)

    # data handling: inner to outer data format
    if case.data_handling['inner_to_outer'] == 'csv':
      # swap the outputDatabase to outputExportOutStreams
      output_node = template.find('Models').find('Code').find('outputDatabase')
      output_node.tag = 'outputExportOutStreams'
      # no need to change name, as database and outstream have the same name



class GaussianProcessRegressor(FeatureDriver):
  def __init__(self):
    super().__init__()
    self._name = "gpROM"

  def _modify_models(self, template, case, components, sources):
    features = get_feature_list(case, components)
    # TODO: Move default values to somewhere they could actually be reached,
    #       like somewhere in the case input specs.
    model_params = {
      "Features": ", ".join(features),
      "Target": build_opt_metric_from_name(case),
      "alpha": 1e-8,
      "n_restarts_optimizer": 5,
      "normalize_y": True,
      "kernel": "Custom",
      "custom_kernel": "(Constant*Matern)",
      "anisotropic": True,
      "multioutput": False
    }
    rom = EntityNode("ROM", "gpROM", "GaussianProcessRegressor", kwarg_subs=model_params)

    # Add to Models node
    models = template.find("Models")
    models.append(rom)


class EnsembleModel(FeatureDriver):
  pass
