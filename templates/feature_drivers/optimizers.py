"""
Optimization features

@author: Jacob Bryan (@j-bryan)
@date: 2024-11-08
"""

from feature_driver import FeatureDriver, FeatureCollection
from .samplers import StratifiedSampler
from .models import GaussianProcessRegressor


# TODO: move to template driver
# class Optimizer(FeatureCollection):
#   def edit_template(self, template, case, components, sources):
#     if case.get_opt_strategy() == "BayesianOpt":
#       self._features = [BayesianOpt(),
#                         OptimizationSettings("BayesianOptimizer")]
#     elif case.get_opt_strategy() == "GradientDescent":
#       self._features = [GradientDescent(),
#                         OptimizationSettings("GradientDescent")]
#     super().edit_template(template, case, components, sources)


class BayesianOptimizer(FeatureCollection):
  def __init__(self):
    super().__init__()
    sampler_name = "LHS_samp"
    gp_rom_name = "gpROM"
    self._features = [
                      BayesianOpt(sampler_name, gp_rom_name),
                      StratifiedSampler(sampler_name),
                      GaussianProcessRegressor(gp_rom_name),
                      OptimizationSettings("BayesianOptimizer")]


class BayesianOpt(FeatureDriver):
  pass


class GradientDescentOptimizer(FeatureCollection):
  def __init__(self):
    super().__init__()
    self._features = [GradientDescent(),
                      OptimizationSettings("GradientDescent")]


class GradientDescent(FeatureDriver):
  pass


class OptimizationSettings(FeatureDriver):
  """
  Defines common optimizer options
  """
  def __init__(self, optimizer):
    super().__init__()
    self._optimizer = optimizer

  def _modify_optimizers(self, template, case, components, sources):
    optimizer = template.find(f".//Optimizers/{self._optimizer}")
    # convergence
    # sampler init
    # objective
    # TargetEvaluation
