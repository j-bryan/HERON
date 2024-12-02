from .base import RavenSnippet


class Distribution(RavenSnippet):
  def __init__(self, tag: str, name: str, subelements: dict = {}) -> None:
    super().__init__(tag, name, class_name="Distributions", subelements=subelements)


class UniformDistribution(Distribution):
  def __init__(self, name: str, lower_bound: float, upper_bound: float) -> None:
    bounds = {
      "lowerBound": lower_bound,
      "upperBound": upper_bound
    }
    super().__init__("Uniform", name, subelements=bounds)


# Normal
# Beta
# Poisson
