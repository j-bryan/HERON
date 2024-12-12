import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets import PointSet, HistorySet, DataSet
sys.path.pop()

import unittest
import xml.etree.ElementTree as ET


class TestDataObjectBase:
  def test_snippet_class(self):
    self.assertEqual(self.obj.snippet_class, "DataObjects")

  def test_inputs(self):
    self.assertListEqual(self.obj.inputs, [])
    self.obj.inputs.append("inp1")
    self.assertListEqual(self.obj.inputs, ["inp1"])
    self.assertListEqual(self.obj.find("Input").text, ["inp1"])

  def test_outputs(self):
    self.assertListEqual(self.obj.outputs, [])
    self.obj.outputs.append("out1")
    self.assertListEqual(self.obj.outputs, ["out1"])
    self.assertListEqual(self.obj.find("Output").text, ["out1"])


class TestPointSet(unittest.TestCase, TestDataObjectBase):
  def setUp(self):
    self.obj = PointSet()

  def test_tag(self):
    self.assertEqual(self.obj.tag, "PointSet")


class TestHistorySet(unittest.TestCase, TestDataObjectBase):
  def setUp(self):
    self.obj = HistorySet()

  def test_tag(self):
    self.assertEqual(self.obj.tag, "HistorySet")


class TestDataSet(unittest.TestCase, TestDataObjectBase):
  def setUp(self):
    self.obj = DataSet()

  def test_tag(self):
    self.assertEqual(self.obj.tag, "DataSet")

  def test_add_index(self):
    self.obj.add_index("index_var", "some_var")
    index_node = self.obj.find("Index[@var='index_var']")
    self.assertIsNotNone(index_node)
    self.assertEqual(index_node.text, "some_var")

    self.obj.add_index("another_index", ["var1", "var2"])
    index_node = self.obj.find("Index[@var='another_index']")
    self.assertIsNotNone(index_node)
    self.assertEqual(index_node.text, ["var1", "var2"])
