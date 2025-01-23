# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Decorators
  @author: Jacob Bryan (@j-bryan)
  @date: 2024-12-11
"""
from typing import Any


def _coerce_to_list(value: Any) -> list[Any]:
  """
  Try to make value a list that makes sense. Special handling for strings is taken to avoid splitting a
  string into characters. If commas are present in the string, it is assumed the string has comma-delimited
  values.
  @ In, value, Any, the value to coerce
  @ Out, coerced, list[Any], the coerced value object
  """
  if not value:
    # empty Collections (list, set, tuple, str, dict, ...) or None are all falsy
    coerced = []
  elif isinstance(value, str):
    # strings: either a comma-delimited list of values in the string or just a single item
    if "," in value:
      coerced = [s.strip() for s in value.split(",")]
    else:
      coerced = [value]
  else:
    # Just try coercing to a list otherwise and hope for the best. This should work without throwing
    # an exception for anything iterable.
    coerced = list(value)
  return coerced


class ListWrapper(list):
  """
  A wrapper class which emulates a list (and subclasses list for duck typing) which interfaces with a property
  """
  def __init__(self, property_instance, obj):
    self.property_instance = property_instance
    self.obj = obj

  def _get_list(self):
    return _coerce_to_list(self.property_instance.fget(self.obj))

  def _set_list(self, value):
    self.property_instance.fset(self.obj, _coerce_to_list(value))

  def __getitem__(self, index):
    return self._get_list()[index]

  def __setitem__(self, index, value):
    lst = self._get_list()
    lst[index] = value
    self._set_list(lst)

  def __delitem__(self, index):
    lst = self._get_list()
    del lst[index]
    self._set_list(lst)

  def append(self, obj):
    lst = self._get_list()
    lst.append(obj)
    self._set_list(lst)

  def extend(self, iterable):
    lst = self._get_list()
    lst.extend(iterable)
    self._set_list(lst)

  def insert(self, index, obj):
    lst = self._get_list()
    lst.insert(index, obj)
    self._set_list(lst)

  def remove(self, value):
    lst = self._get_list()
    lst.remove(value)
    self._set_list(lst)

  def pop(self, index=-1):
    lst = self._get_list()
    val = lst.pop(index)
    self._set_list(lst)
    return val

  def clear(self):
    self._set_list([])

  def index(self, value):
    return self._get_list().index(value)

  def count(self, value):
    return self._get_list().count(value)

  def sort(self, *, key=None, reverse=False):
    lst = self._get_list()
    lst.sort(key=key, reverse=reverse)
    self._set_list(lst)

  def reverse(self) -> None:
    lst = self._get_list()
    lst.reverse()
    self._set_list(lst)

  def copy(self):
    return self._get_list().copy()

  def __len__(self):
    return len(self._get_list())

  def __iter__(self):
    return iter(self._get_list())

  def __repr__(self):
    return repr(self._get_list())

  def __eq__(self, other):
    return self._get_list() == other

  def __contains__(self, value):
    return value in self._get_list()


class listproperty:
  """
  A approximation of the built-in "property" function/decorator, with additional logic for getting/setting values
  which are lists (or more precisely, ListWrapper objects) in a way that allows for list operations (e.g. append,
  extend, insert) on the property.
  """
  def __init__(self, fget=None, fset=None, fdel=None, doc=None):
    self.fget = fget
    self.fset = fset
    self.fdel = fdel
    if doc is None and fget is not None:
      doc = fget.__doc__
    self.__doc__ = doc

  def __set_name__(self, owner, name):
      self.__name__ = name

  def __get__(self, obj, objtype=None):
    if obj is None:
      return self
    if self.fget is None:
      raise AttributeError("unreadable attribute")
    return ListWrapper(self, obj)

  def __set__(self, obj, value):
    if self.fset is None:
      raise AttributeError("can't set attribute")
    self.fset(obj, value)

  def __delete__(self, obj):
    if self.fdel is None:
      raise AttributeError("can't delete attribute")
    self.fdel(obj)

  def getter(self, fget):
    """
    Set getter function for property
    @ In, fget, Callable, getter function
    @ Out, obj, self with set getter
    """
    return type(self)(fget, self.fset, self.fdel, self.__doc__)

  def setter(self, fset):
    """
    Set setter function for property
    @ In, fget, Callable, setter function
    @ Out, obj, self with set setter
    """
    return type(self)(self.fget, fset, self.fdel, self.__doc__)

  def deleter(self, fdel):
    """
    Set deleter function for property
    @ In, fdel, Callable, deleter function
    @ Out, obj, self with set deleter
    """
    return type(self)(self.fget, self.fset, fdel, self.__doc__)
