import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets import IOStep, MultiRun, PostProcess
sys.path.pop()

import pytest
import xml.etree.ElementTree as ET


@pytest.fixture
def setup_iostep():
  return IOStep("write_step")

@pytest.fixture
def setup_iostep_from_xml():
  xml = """
  <IOStep name="write_step">
    <Input class="DataObjects" type="PointSet">point_set</Input>
    <Input class="DataObjects" type="DataSet">data_set</Input>
    <Output class="OutStreams" type="Print">print_point_set</Output>
    <Output class="OutStreams" type="Print">print_data_set</Output>
    <Output class="OutStreams" type="Plot">plot_point_set</Output>
  </IOStep>
  """
  return IOStep.from_xml(xml)
