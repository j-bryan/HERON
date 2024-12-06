import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets import VariableGroup
sys.path.pop()

import pytest
import xml.etree.ElementTree as ET


class TestVariableGroup:
  @pytest.fixture(scope="class")
  def setup_default(self):
    return VariableGroup(name="GRO_group")

  @pytest.fixture(scope="class")
  def setup_from_xml(self):
    xml = "<Group name='GRO_group'>var1, var2,var3</Group>"  # NOTE: intentionally bad spacing
    root = ET.fromstring(xml)
    return VariableGroup.from_xml(root)

  def test_default(self, setup_default):
    assert setup_default.snippet_class == "VariableGroups"
    assert setup_default.tag == "Group"
    assert setup_default.name == "GRO_group"
    assert setup_default._variables == []

  def test_from_xml(self, setup_from_xml):
    assert setup_from_xml.snippet_class == "VariableGroups"
    assert setup_from_xml.tag == "Group"
    assert setup_from_xml.name == "GRO_group"
    assert setup_from_xml._variables == ["var1", "var2", "var3"]

  def test_add_variables(self, setup_default):
    setup_default.add_variables("var1", "var2", "var3")
    assert setup_default._variables == ["var1", "var2", "var3"]
    assert setup_default.text == ["var1", "var2", "var3"]

    setup_default.add_variables(["var3", "var4"])
    assert setup_default._variables == ["var1", "var2", "var3", "var4"]
