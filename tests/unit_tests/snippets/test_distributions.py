import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets import distributions
sys.path.pop()

import pytest
import importlib
import xml.etree.ElementTree as ET

# Limited testing of all allowable distributions
# We can easily test the construction (with __init__ or from_xml) by looping over distribution names.
# It's more difficult to automate testing of property getting/setting, so we reserve that resolution of
# testing for a couple of the most commonly used distributions.

dists = [
  "Beta",
  "Exponential",
  "Gamma",
  "Laplace",
  "Logistic",
  "LogNormal",
  "LogUniform",
  "Normal",
  "Triangular",
  "Uniform",
  "Weibull",
  "Custom1D",
  "Bernoulli",
  "Binomial",
  "Geometric",
  "Poisson",
  "Categorical",
  "UniformDiscrete",
  "MarkovCategorical",
  "MultivariateNormal",
  "NDInverseWeight",
  "NDCartesianSpline"
]

@pytest.mark.parametrize("dist_name", dists)
def test_constructed_distributions(dist_name):
  cls = getattr(distributions, dist_name)
  assert cls.snippet_class == "Distributions"
  assert cls.tag == dist_name


@pytest.mark.parametrize("dist_name", dists)
def test_from_xml(dist_name):
  cls = getattr(distributions, dist_name)
  xml = f"<{dist_name} name='new_dist'/>"
  root = ET.fromstring(xml)
  dist = cls.from_xml(root)

  assert dist.snippet_class == "Distributions"
  assert dist.tag == dist_name
  assert dist.name == "new_dist"

# Explicit testing of just a couple of the most common distributions we expect to see in HERON.

class TestUniform:
  @pytest.fixture(scope="class")
  def setup_default(self):
    return distributions.Uniform("unif_dist")

  @pytest.fixture(scope="class")
  def setup_from_xml(self):
    xml = """
    <Uniform name="unif_dist">
      <lowerBound>-1</lowerBound>
      <upperBound>3</upperBound>
    </Uniform>
    """
    root = ET.fromstring(xml)
    return distributions.Uniform.from_xml(root)

  def test_from_xml(self, setup_from_xml):
    assert setup_from_xml.lower_bound == -1
    assert setup_from_xml.upper_bound == 3

  def test_bounds(self, setup_default):
    setup_default.lower_bound = 0
    assert setup_default.find("lowerBound").text == 0
    setup_default.upper_bound = 1
    assert setup_default.find("upperBound").text == 1


class TestNormal:
  @pytest.fixture(scope="class")
  def setup_default(self):
    return distributions.Normal("norm_dist")

  @pytest.fixture(scope="class")
  def setup_from_xml(self):
    xml = """
    <Normal name="norm_dist">
      <mean>0</mean>
      <sigma>1</sigma>
    </Normal>
    """
    root = ET.fromstring(xml)
    return distributions.Normal.from_xml(root)

  def test_from_xml(self, setup_from_xml):
    assert setup_from_xml.mean == 0
    assert setup_from_xml.sigma == 1

  def test_params(self, setup_default):
    setup_default.mean = -1
    assert setup_default.find("mean").text == -1
    setup_default.sigma = 10
    assert setup_default.find("sigma").text == 10
