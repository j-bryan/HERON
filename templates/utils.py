import re
import itertools
from typing import Any
import xml.etree.ElementTree as ET


def get_stat_prefixes(stat_names: list[str], case) -> list[str]:
  """
  Get all statistics prefixes for a list of statistic names
  @ In, stat_names, list[str], names of statistics
  @ In, case, Case, HERON case
  @ Out, stat_prefixes, list[str], list of statistics prefixes
  """
  stat_prefixes = []
  for stat in stat_names:
    stat_meta = case.stats_metrics_meta[stat]
    prefix = stat_meta["prefix"]

    # Are there additional attributes? If so, we need to loop over these.
    stat_attribs = {k: stat_meta[k] for k in stat_meta.keys() & {"percent", "threshold"}}

    if not stat_attribs:
      stat_prefixes.append(prefix)
    else:
      for val in stat_attribs.values():
        if isinstance(val, list):
          stat_prefixes.extend([f"{prefix}_{v}" for v in val])
        else:
          stat_prefixes.append(f"{prefix}_{val}")

  return stat_prefixes


def get_result_stats(names: list[str], stats: list[str], case, naming_template: str):
  """
    Constructs the names of the statistics requested for output
    @ In, names, list[str], result metric names (economics, component activities)
    @ In, stats, list[str], statistic names
    @ In, case, HERON Case, defining Case instance
    @ In, naming_template, str, template for naming results statistics
    @ Out, names, list, list of names of statistics requested for output
  """
  stat_prefixes = get_stat_prefixes(stats, case)
  stat_names = [naming_template.format(prefix=prefix, name=name) for prefix, name in itertools.product(stat_prefixes, names)]
  return stat_names


def get_statistical_results_vars(case, components: list, default_stats: list[str], financial_stats: list[str], naming_templates: dict[str, str] = {}) -> list[str]:
  """
  Collects result metric names for statistical metrics
  @ In, case, Case, HERON case
  @ In, components, list[Component], HERON components
  @ Out, var_names, list[str], list of variable names
  """
  # Add statistics for economic metrics to variable group. Use all statistics.
  stats_names = set(default_stats) | set(case.get_result_statistics())
  econ_metrics = case.get_econ_metrics(nametype="output")
  stats_var_default_template = "{prefix}_{name}"
  stats_var_names = get_result_stats(econ_metrics, stats_names, case, naming_templates.get("statistic", stats_var_default_template))

  # Add total activity statistics for variable group. Use only non-financial statistics.
  non_fin_stat_names = stats_names - set(financial_stats)
  # tot_activity_metrics = self._get_activity_metrics(components)
  tot_act_default_template = "TotalActivity__{component}__{tracker}__{resource}"
  tot_activity_metrics = get_component_activity_vars(components, naming_templates.get("tot_activity", tot_act_default_template))
  activity_var_names = get_result_stats(tot_activity_metrics, non_fin_stat_names, case)

  var_names = stats_var_names + activity_var_names

  return var_names


def get_capacity_vars(components, name_template, debug=False) -> dict[str, Any]:
  """
  Get dispatch variable names
  @ In, components, list, list of HERON components
  @ In, name_template, str, naming template for dispatch variable name, expecting
                            keywords "component", "tracker", and "resource"
  @ Out, vars, dict, variable name-value pairs
  """
  vars = {}

  for component in components:
    name = component.name
    # treat capacity
    ## we just need to make sure everything we need gets into the dispatch ensemble model.
    ## For each interaction of each component, that means making sure the Function, ARMA, or constant makes it.
    ## Constants from outer (namely sweep/opt capacities) are set in the MC Sampler from the outer
    ## The Dispatch needs info from the Outer to know which capacity to use, so we can't pass it from here.
    capacity = component.get_capacity(None, raw=True)

    if capacity.is_parametric():
      # this capacity is being [swept or optimized in outer] (list) or is constant (float)
      # -> so add a node, put either the const value or a dummy in place
      cap_name = name_template.format(unit=name, feature='capacity')
      values = capacity.get_value(debug=debug)
      vars[cap_name] = values
    elif capacity.type in ['StaticHistory', 'SyntheticHistory', 'Function', 'Variable']:
      # capacity is limited by a signal, so it has to be handled in the dispatch; don't include it here.
      # OR capacity is limited by a function, and we also can't handle it here, but in the dispatch.
      pass
    else:
      raise NotImplementedError

  return vars


def get_component_activity_vars(components: list, name_template: str) -> list[str]:
  """
  Get dispatch variable names
  @ In, components, list, list of HERON components
  @ In, name_template, str, naming template for dispatch variable name, expecting
                            keywords "component", "tracker", and "resource"
  @ Out, vars, list[str], list of variable names
  """
  vars = []

  for component in components:
    name = component.name
    for tracker in component.get_tracking_vars():
      resource_list = sorted(list(component.get_resources()))
      for resource in resource_list:
        var_name = name_template.format(component=name, tracker=tracker, resource=resource)
        vars.append(var_name)

  return vars


def parse_xpath(xpath: str):
  """
  Parses an XPath with possible attributes and text content into a list of dictionaries.
  Each dictionary contains "tag" and "attrib" keys.
  @ In, xpath, str, an XPath describing a tree of nodes
  @ Out, nodes, list[dict[str, str]], list of dicts describing the nodes of the tree described by the XPath
  """
  # Regular expression to match node with optional attributes
  # Regex for XPaths created using AiVA
  node_pattern = re.compile(r"(?P<tag>[^/\[]+)(\[@(?P<attrib>[^=]+)=(?P<quote>['\"])(?P<value>[^'\"]+)(?P=quote)\])?")

  nodes = []
  for match in node_pattern.finditer(xpath.strip('/')):
    tag = match.group('tag')
    attrib = {match.group('attrib'): match.group('value')} if match.group('attrib') else {}
    nodes.append({'tag': tag, 'attrib': attrib})

  return nodes

def add_node_to_tree(child_node: ET.Element, parent_path: str, root: ET.Element) -> None:
  """
  Adds a child XML node to a parent node specified by an XPath.
  Creates any necessary intermediate nodes with attributes and text if they do not exist.

  @ In, child_node, ET.Element, object representing the child node to be added
  @ In, xpath, str, string representing the XPath to the parent node
  @ In, root, ET.Element,
  """
  # Parse the XPath into nodes with tag, attributes, and text
  path_parts = parse_xpath(parent_path)

  # Start from the root
  current_node = root

  for node_xpath, parsed in zip(parent_path.strip("/").split("/"), path_parts):
    # Find the next node by xpath
    next_node = current_node.find(node_xpath)
    if next_node is None:
      # Make the node with the parsed tag and attributes
      next_node = ET.SubElement(current_node, parsed["tag"], attrib=parsed["attrib"])
    current_node = next_node

  # Append the child node to the current (parent) node
  current_node.append(child_node)

def stringify_node_values(node):
    """
    Ensure that XML node attribute and text values are strings before trying to express the XML tree as a string
    that is written to file. Traverses the XML tree recursively.
    @ In, node, ET.Element, node to begin traversal at
    @ Out, None
    """
    for k, v in node.attrib.items():
      node.attrib[k] = _to_string(v)

    text = node.text
    if text is not None and not isinstance(text, str):
      node.text = _to_string(node.text)

    # Traverse children
    for child in node:
        stringify_node_values(child)

def _to_string(val: Any, delimiter: str = ", ") -> str:
  """
  Express the provided object as an appropriate string for a node text. If it's a string or numeric type,
  those can easily be expressed as strings. If the object is list-like (list, tuple, set, numpy array, etc.),
  the object elements are joined in a comma-separated list. Mappings like dictionaries are not supported.

  @ In, val, Any, value to be converted to string for node text
  @ In, delimiter, str, string used to delimit iterator items
  @ out, text, str, string representative of the value
  """
  if isinstance(val, str):
    return val
  elif isinstance(val, dict):
    raise TypeError(f"Unable to convert dicts to node text. Received type '{type(val)}'.")
  elif hasattr(val, "__iter__") and not isinstance(val, str):  # lists, sets, numpy arrays, etc.
    # return as comma-separated string
    return delimiter.join([str(v) for v in val])
  else:  # numeric types and other objects, including RavenSnippet objects
    return str(val)

def find_node(parent: ET.Element, tag: str, make_if_missing: bool = True) -> ET.Element | None:
  """
  Find the first node with tag in parent
  @ In, parent, ET.Element, parent node
  @ In, tag, str, tag of node to find
  @ In, make_if_missing, bool, optional, make a node with the given tag if one is not found
  @ Out, node, ET.Element, the found or created node
  """
  node = parent.find(tag)
  if node is None and make_if_missing:
    node = parent
    for child_params in parse_xpath(tag):
      node = ET.SubElement(node, child_params["tag"], child_params["attrib"])
  return node

def get_node_index(parent: ET.Element, child: ET.Element) -> int | None:
  """
  Get the index of a node in its parent
  @ In, parent, ET.Element, parent node
  @ In, child, ET.Element, child node
  @ Out, index, int | None, index of the child (None if not found)
  """
  for i, sub in enumerate(parent):
    if child == sub:
      return i
  return None


def node_property(cls: ET.Element, prop_name: str, node_tag: str | None = None, default=None):
  """
  Creates a class property that gets/sets a child node text value
  @ In, cls, ET.Element, the ET.Element class or a subclass of it
  @ In, prop_name, str, property name
  @ In, node_tag, str | None, optional, tag or path of the node the property is tied to (default=prop_name)
  @ In, default, Any, optional, the default getter value
  @ Out, None
  """
  if node_tag is None:
    node_tag = prop_name

  def getter(self):
    node = self.find(node_tag)
    return default if node is None else node.text

  def setter(self, val):
    find_node(self, node_tag).text = val

  def deleter(self):
    if (node := self.find(node_tag)) is not None:
      self.remove(node)

  doc = f"Accessor property for '{node_tag}' node text"
  setattr(cls, prop_name, property(getter, setter, deleter, doc=doc))


def attrib_property(cls: ET.Element, prop_name: str, attrib_name: str | None = None, default=None):
  """
  Creates a class property that gets/sets a node attribute value
  @ In, cls, ET.Element, the ET.Element class or a subclass of it
  @ In, prop_name, str, property name
  @ In, attrib_name, str | None, optional, name of the node attribute the property is tied to (default=prop_name)
  @ In, default, Any, optional, the default getter value
  @ Out, None
  """
  if attrib_name is None:
    attrib_name = prop_name

  def getter(self):
    return self.get(attrib_name, default)

  def setter(self, val):
    self.set(attrib_name, val)

  def deleter(self):
    self.attrib.pop(attrib_name, None)

  doc = f"Accessor property for '{attrib_name}' node attribute"
  setattr(cls, prop_name, property(getter, setter, deleter))
