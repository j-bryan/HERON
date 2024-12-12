import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets import File
sys.path.pop()

import unittest
import xml.etree.ElementTree as ET


class TestFile(unittest.TestCase):
  def setUp(self):
    self.file = File()

    xml = "<Input name='raven_inner' type='raven'>path/to/inner.xml</Input>"
    root = ET.fromstring(xml)
    self.file_xml = File.from_xml(root)

  def test_snippet_class(self):
    self.assertEqual(self.file.snippet_class, "Files")

  def test_tag(self):
    self.assertEqual(self.file.tag, "Input")

  def test_from_xml(self):
    self.assertEqual(self.file_xml.name, "raven_inner")
    self.assertEqual(self.file_xml.get("name"), "raven_inner")
    self.assertEqual(self.file_xml.type, "raven")
    self.assertEqual(self.file_xml.get("type"), "raven")
    self.assertEqual(self.file_xml.path, "path/to/inner.xml")
    self.assertEqual(self.file_xml.text, "path/to/inner.xml")

  def test_type(self):
    self.assertIsNone(self.file.type)
    type = "some_type"
    self.file.type = type
    self.assertEqual(self.file.type, type)
    self.assertEqual(self.file.get("type"), type)

  def test_path(self):
    self.assertIsNone(self.file.path)
    path = "path/to/file.xml"
    self.file.path = path
    self.assertEqual(self.file.path, path)
    self.assertEqual(self.file.text, path)

  def test_to_assembler_node(self):
    xml1 = """<Input name="inner_workflow" type="raven">../inner.xml</Input>"""
    file1 = File.from_xml(ET.fromstring(xml1))
    assemb1 = file1.to_assembler_node("File")
    self.assertEqual(assemb1.tag, "File")
    self.assertDictEqual(assemb1.attrib, {"class": "Files", "type": "raven"})
    self.assertEqual(assemb1.text, "inner_workflow")

    xml2 = """<Input name="heron_lib">../heron.lib</Input>"""
    file2 = File.from_xml(ET.fromstring(xml2))
    assemb2 = file2.to_assembler_node("File")
    self.assertEqual(assemb2.tag, "File")
    # getting this "type" value right is a deviation from the usual RavenSnippet.to_assemb_node() method
    self.assertDictEqual(assemb2.attrib, {"class": "Files", "type": ""})
    self.assertEqual(assemb2.text, "heron_lib")
