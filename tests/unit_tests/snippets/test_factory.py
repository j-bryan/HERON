import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets.factory import SnippetFactory
sys.path.pop()

import unittest
import xml.etree.ElementTree as ET


class MockBase:
  tag = None
  subtype = None

  @classmethod
  def get(cls, key, default=None):
    return getattr(cls, key, default)


class Mock(MockBase):
  tag = "mock"
  subtype = None


class MockA(MockBase):
  tag = "mock"
  subtype = "a"


class MockB(MockBase):
  tag = "mock"
  subtype = "b"


class TestSnippetFactory(unittest.TestCase):
  """ Tests for the SnippetFactory class """
  def setUp(self):
    self.factory = SnippetFactory()

  def test_register_snippet_class(self):
    # Add a snippet class
    self.factory.register_snippet_class(Mock)
    self.assertIn(f"mock", self.factory.registered_classes)
    num_registered = len(self.factory.registered_classes)

    # Giving a new class with the same tag/subtype combo should throw an error
    class Mock2(MockBase):
      tag = "mock"
      subtype = None

    with self.assertRaises(ValueError):
      self.factory.register_snippet_class(Mock2)

    # Giving the snippet what looks like a RavenSnippet base class shouldn't raise an
    # error but it also shouldn't be added as a registered class since it has no tag.
    self.factory.register_snippet_class(MockBase)
    self.assertEqual(len(self.factory.registered_classes), num_registered)

  def test_register_all_subclasses(self):
    self.factory.register_all_subclasses(MockBase)
    gold = {
      "mock": Mock,
      "mock[@subType='a']": MockA,
      "mock[@subType='b']": MockB,
    }
    self.assertDictEqual(self.factory.registered_classes, gold)

  def test_has_registered_class(self):
    # Add a snippet class
    self.factory.register_snippet_class(Mock)
    # See if the class is found for a matching node
    node = ET.Element("mock")
    self.assertTrue(self.factory.has_registered_class(node))
    node_a = ET.Element("mock", subType="a")
    self.assertFalse(self.factory.has_registered_class(node_a))  # not registered

  def test_get_snippet_class_key(self):
    # Get the key of a snippet-like class
    key = self.factory._get_snippet_class_key(Mock)
    self.assertEqual(key, "mock")

    # Get the key of a snippet-like class with a subtype attribute
    key = self.factory._get_snippet_class_key(MockA)
    self.assertEqual(key, "mock[@subType='a']")

  def test_get_node_key(self):
    # Get the key of an ET.Element
    node = ET.Element("element")
    key = self.factory._get_node_key(node)
    self.assertEqual(key, "element")

    # Get the key of an ET.Element with a subType attribute
    node = ET.Element("element", subType="st")
    key = self.factory._get_node_key(node)
    self.assertEqual(key, "element[@subType='st']")
