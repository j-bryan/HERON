"""
Unit tests for the listproperty decorator

@author: Jacob Bryan (@j-bryan)
@date: 2024-12-11
"""

import sys
import os
import unittest

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*3))
sys.path.append(HERON_LOC)

from HERON.templates.decorators import listproperty
sys.path.pop()


class ListPropertyTester:
  def __init__(self):
    self._list = []

  @listproperty
  def prop(self) -> list[str]:
    return self._list

  @prop.setter
  def prop(self, lst: list[str]) -> None:
    self._list = lst


class TestListProperty(unittest.TestCase):
  def setUp(self):
    self.tester = ListPropertyTester()

  def test_get(self):
    self.assertListEqual(self.tester.prop, [])

  def test_set(self):
    lst = ["1", "2", "3"]
    self.tester.prop = lst
    self.assertListEqual(self.tester.prop, lst)

  def test_append(self):
    self.tester.prop.append("a")
    self.assertListEqual(self.tester.prop, ["a"])
    self.tester.prop.append("b")
    self.assertListEqual(self.tester.prop, ["a", "b"])

  def test_clear(self):
    self.tester.prop = ["b", "c"]
    self.tester.prop.clear()
    self.assertListEqual(self.tester.prop, [])

  def test_copy(self):
    lst = ["b", "c"]
    self.tester.prop = lst
    copied = self.tester.prop.copy()
    self.assertListEqual(self.tester.prop, lst)
    self.assertListEqual(copied, lst)

  def test_count(self):
    lst = ["a", "b", "c", "a"]
    self.tester.prop = lst
    self.assertEqual(self.tester.prop.count("a"), lst.count("a"))
    self.assertEqual(self.tester.prop.count("b"), lst.count("b"))

  def test_extend(self):
    self.tester.prop.extend(["a", "b"])
    self.assertListEqual(self.tester.prop, ["a", "b"])
    self.tester.prop.extend(["c"])
    self.assertListEqual(self.tester.prop, ["a", "b", "c"])

  def test_index(self):
    lst = ["a", "b", "c", "a"]
    self.tester.prop = lst
    self.assertEqual(self.tester.prop.index("a"), lst.index("a"))
    self.assertEqual(self.tester.prop.index("b"), lst.index("b"))
    self.assertEqual(self.tester.prop.index("c"), lst.index("c"))

  def test_insert(self):
    self.tester.prop = ["b", "c"]
    self.tester.prop.insert(0, "a")
    self.assertListEqual(self.tester.prop, ["a", "b", "c"])

  def test_pop(self):
    self.tester.prop = ["a", "b", "c"]
    popped = self.tester.prop.pop()
    self.assertEqual(popped, "c")
    self.assertListEqual(self.tester.prop, ["a", "b"])
    popped = self.tester.prop.pop(0)
    self.assertEqual(popped, "a")
    self.assertListEqual(self.tester.prop, ["b"])

    # pop from empty list
    self.tester.prop = []
    with self.assertRaises(IndexError):
      self.tester.prop.pop()

  def test_remove(self):
    self.tester.prop = ["b", "c"]
    self.tester.prop.remove("b")
    self.assertListEqual(self.tester.prop, ["c"])

  def test_reverse(self):
    self.tester.prop = ["b", "c"]
    self.tester.prop.reverse()
    self.assertListEqual(self.tester.prop, ["c", "b"])

  def test_sort(self):
    lst = ["a", "b", "c", "a"]
    self.tester.prop = lst
    lst_sorted = sorted(lst)
    self.tester.prop.sort()
    self.assertListEqual(self.tester.prop, lst_sorted)
