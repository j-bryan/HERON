import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets import NetCDF, HDF5
sys.path.pop()

import unittest
import xml.etree.ElementTree as ET


class TestDatabasesBase:
  def test_snippet_class(self):
    self.assertEqual(self.db.snippet_class, "Databases")

  def test_read_mode(self):
    self.assertIsNone(self.db.read_mode)
    self.db.read_mode = "overwrite"
    self.assertEqual(self.db.read_mode, "overwrite")
    self.assertEqual(self.db.get("readMode"), "overwrite")

  def test_directory(self):
    self.assertIsNone(self.db.directory)
    self.db.directory = "some_dir"
    self.assertEqual(self.db.directory, "some_dir")
    self.assertEqual(self.db.get("directory"), "some_dir")

  def test_filename(self):
    self.assertIsNone(self.db.filename)
    self.db.filename = "some_file"
    self.assertEqual(self.db.filename, "some_file")
    self.assertEqual(self.db.get("filename"), "some_file")

  def test_variables(self):
    self.assertListEqual(self.db.variables, [])
    self.db.variables.append("some_var")
    self.assertListEqual(self.db.variables, ["some_var"])
    self.assertListEqual(self.db.find("variables").text, ["some_var"])


class TestNetCDF(unittest.TestCase, TestDatabasesBase):
  def setUp(self):
    self.db = NetCDF()

  def test_tag(self):
    self.assertEqual(self.db.tag, "NetCDF")


class TestHDF5(unittest.TestCase, TestDatabasesBase):
  def setUp(self):
    self.db = HDF5()

  def test_tag(self):
    self.assertEqual(self.db.tag, "HDF5")

  def test_compression(self):
    self.assertIsNone(self.db.compression)
    self.db.compression = "comp"
    self.assertEqual(self.db.compression, "comp")
    self.assertEqual(self.db.get("compression"), "comp")
