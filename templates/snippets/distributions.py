from .base import RavenSnippet


class Distribution(RavenSnippet):
  snippet_class = "Distributions"

  def __init__(self, name: str, subelements: dict = {}) -> None:
    super().__init__(name, class_name="Distributions", subelements=subelements)


class UniformDistribution(Distribution):
  tag = "Uniform"

  def __init__(self, name: str, lower_bound: float, upper_bound: float) -> None:
    bounds = {
      "lowerBound": lower_bound,
      "upperBound": upper_bound
    }
    super().__init__(name, subelements=bounds)


# Normal
# Beta
# Poisson
