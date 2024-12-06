import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets import File
sys.path.pop()

import pytest
import xml.etree.ElementTree as ET


class TestFile:
  @pytest.fixture(scope="class")
  def setup_file(self):
    xml = "<Input name='raven_inner' type='raven'>path/to/inner.xml</Input>"
    root = ET.fromstring(xml)
    file = File.from_xml(root)
    return file

  def test_from_xml(self, setup_file):
    assert setup_file.name == "raven_inner"
    assert setup_file.type == "raven"
    assert setup_file.text == "path/to/inner.xml"

  def test_name(self, setup_file):
    setup_file.name = "new_name"
    assert setup_file.name == "new_name"
    assert setup_file.get("name") == "new_name"

  def test_type(self, setup_file):
    setup_file.type = "new_type"
    assert setup_file.type == "new_type"
    assert setup_file.get("type") == "new_type"

  def test_snippet_class(self, setup_file):
    assert setup_file.snippet_class == "Files"
