import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.insert(0, HERON_LOC)
print(sys.path)

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
    assert setup_default.variables == []
    assert setup_default.text is None

  def test_from_xml(self, setup_from_xml):
    assert setup_from_xml.snippet_class == "VariableGroups"
    assert setup_from_xml.tag == "Group"
    assert setup_from_xml.name == "GRO_group"
    assert setup_from_xml._variables == ["var1", "var2", "var3"]
    assert setup_from_xml.variables == ["var1", "var2", "var3"]
    assert setup_from_xml.text == ["var1", "var2", "var3"]

  def test_set_variables(self, setup_default):
    setup_default.variables = ["var1", "var2"]
    assert setup_default._variables == ["var1", "var2"]
    assert setup_default.text == ["var1", "var2"]

    setup_default.variables.append("var3")
    assert setup_default._variables == ["var1", "var2", "var3"]

    setup_default.variables.extend(["var4"])
    assert setup_default._variables == ["var1", "var2", "var3", "var4"]
