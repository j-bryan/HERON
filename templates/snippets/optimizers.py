"""
Optimization features

@author: Jacob Bryan (@j-bryan)
@date: 2024-11-08
"""
from typing import Any
import xml.etree.ElementTree as ET

from ..xml_utils import _to_string

from ..xml_utils import find_node
from .base import RavenSnippet
from .samplers import Sampler
from .models import Model
from .dataobjects import DataObject


class Optimizer(Sampler):  # inheriting from Sampler mimics RAVEN inheritance structure
  """ A base class for RAVEN optimizer XML snippets """
  snippet_class = "Optimizers"

  def __init__(self, name: str):
    super().__init__(name)
    # "objective" and "TargetEvaluation" subnodes are required for all optimizers implemented here
    ET.SubElement(self, "objective")
    ET.SubElement(self, "TargetEvaluation")

  def set_objective(self, objective: str):
    obj_node = self.find("objective")
    obj_node.text = _to_string(objective)

  def set_target_data_object(self, data_object: DataObject):
    # The TargetEvaluation node has an assembler node format with the TargetEvaluation tag. It's not really an
    # assembler node, but it follows the same format.
    assemb_node = data_object.to_assembler_node("TargetEvaluation")
    # Copy assembler node info over to the existing TargetEvaluation node
    target_eval = self.find("TargetEvaluation")
    target_eval.attrib.update(assemb_node.attrib)
    target_eval.text = assemb_node.text

  def set_opt_settings(self, opt_settings: dict) -> None:
    """
    Set optimizer settings
    @ In, opt_settings, dict, the optimizer settings
    @ Out, None
    """
    # convergence settings
    convergence = find_node(self, "convergence")
    for k, v in opt_settings.get("convergence", {}).items():
      node = convergence.find(k)
      node.text = _to_string(v)

    # persistence
    if "persistence" in opt_settings:
      persistence = find_node(convergence, "persistence")
      persistence.text = _to_string(opt_settings["persistence"])

    # samplerInit settings
    sampler_init = find_node(self, "samplerInit")
    for name in ["limit", "type"]:  # writeEvery not exposed in HERON input
      if name in opt_settings:
        node = find_node(sampler_init, name)
        node.text = _to_string(opt_settings[name])

#########################
# Bayesian Optimization #
#########################

class BayesianOptimizer(Optimizer):
  tag = "BayesianOptimizer"

  default_settings = {
    "samplerInit": {
      "limit": 100,
      "type": "max",
      "writeSteps": "every",
      # "initialSeed": ""  # initialSeed not included here so the RAVEN default internal seed is used if not provided
    },
    "ModelSelection": {
      "Duration": 1,
      "Method": "Internal"
    },
    "convergence": {
      "acquisition": 1e-5,
      "persistence": 4
    },
    # NOTE: Acquisition function defaults are handled by the the AcquisitionFunction class. Adding the "Acquisition"
    #       key here just ensures the creation of the <Acquisition> child node.
    "Acquisition": ""
  }

  def __init__(self, name: str):
    super().__init__(name)
    # Set settings to default on initialization. Can be modified later via the set_opt_settings method.
    self.add_subelements(self.default_settings)

  def set_opt_settings(self, opt_settings):
    super().set_opt_settings(opt_settings)

    bo_settings = opt_settings["algorithm"]["BayesianOpt"]

    # acquisition function
    acquisition = self.find("Acquisition")
    acq_func_name = bo_settings.get("acquisition", "ExpectedImprovement")
    acq_funcs = {
      "ExpectedImprovement": ExpectedImprovement,
      "ProbabilityOfImprovement": ProbabilityOfImprovement,
      "LowerConfidenceBound": LowerConfidenceBound
    }
    try:
      # FIXME: No acquisition function parameters are exposed to the HERON user
      acq_func = acq_funcs.get(acq_func_name)()
      acquisition.append(acq_func)
    except KeyError:
      raise ValueError(f"Unrecognized acquisition function {acq_func_name}. Allowed: {acq_funcs.keys()}")

    # random seed
    if "seed" in bo_settings:
      sampler_init = find_node(self, "samplerInit")
      initial_seed = find_node(sampler_init, "initialSeed")
      initial_seed.text = _to_string(bo_settings["seed"])

    # modelSelection
    model_selection = find_node(self, "ModelSelection")
    for k, v in bo_settings.get("ModelSelection", {}):
      node = find_node(model_selection, k)
      node.text = _to_string(v)

  def set_sampler(self, sampler: Sampler) -> None:
    if (sampler_node := self.find("Sampler")) is not None:
      self.remove(sampler_node)
    self.append(sampler.to_assembler_node("Sampler"))

  def set_rom(self, rom: Model) -> None:
    if (rom_node := self.find("ROM")) is not None:
      self.remove(rom_node)
    self.append(rom.to_assembler_node("ROM"))

class ExpectedImprovement(RavenSnippet):
  tag = "ExpectedImprovement"

  default_settings = {
    "optimizationMethod": "differentialEvolution",
    "seedingCount": 30
  }

  def __init__(self, settings: dict = {}) -> None:
    settings = self.default_settings | settings
    super().__init__(subelements=settings)

class ProbabilityOfImprovement(RavenSnippet):
  tag = "ProbabilityOfImprovement"

  default_settings = {
    "optimizationMethod": "differentialEvolution",
    "seedingCount": 30,
    "epsilon": 1,
    "rho": 20,
    "transient": "Constant"
  }

  def __init__(self, settings: dict = {}) -> None:
    settings = self.default_settings | settings
    super().__init__(subelements=settings)

class LowerConfidenceBound(RavenSnippet):
  tag = "LowerConfidenceBound"

  default_settings = {
    "optimizationMethod": "differentialEvolution",
    "seedingCount": 30,
    "epsilon": 1,
    "rho": 20,
    "transient": "Constant"
  }

  def __init__(self, settings: dict = {}) -> None:
    settings = self.default_settings | settings
    super().__init__(subelements=settings)


####################
# Gradient Descent #
####################

class GradientDescent(Optimizer):
  tag = "GradientDescent"

  default_settings = {
    "gradient": {  # CentralDifference, SPSA not exposed in HERON input
      "FiniteDifference": ""  # gradDistanceScalar option not exposed
    },
    "convergence": {
      "persistence": 1,
      "gradient": 1e-4,
      "objective": 1e-8
    },
    "stepSize": {
      "GradientHistory": {
        "growthFactor": 2,
        "shrinkFactor": 1.5,
        "initialStepScale": 0.2
      }
    },
    "acceptance": {
      "Strict": ""
    }
  }

  def __init__(self, name: str) -> None:
    super().__init__(name)
    self.add_subelements(self.default_settings)

  def set_opt_settings(self, opt_settings: dict) -> None:
    super().set_opt_settings(opt_settings)

    gd_settings = opt_settings["algorithm"]["GradientDescent"]

    # stepSize settings
    step_size = find_node(self, "stepSize")
    grad_history = find_node(step_size, "GradientHistory")
    for name in ["growthFactor", "shrinkFactor", "initStepScale"]:
      if name in gd_settings:
        node = find_node(grad_history, name)
        node.text = _to_string(gd_settings[name])
