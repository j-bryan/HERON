from typing import Any
import xml.etree.ElementTree as ET

def increment(item, d):
  item = item.strip().rsplit("_", 1)[0] + f"_{d}"
  return item

def alias_to_xpath(alias: str) -> str:
    """
    Convert RAVEN alias syntax to an XPath
    @ In, alias, str, alias path
    @ Out, xpath, str, the equivalent xpath
    """
    # Split the alias path by '|'
    parts = alias.split("|")

    # Initialize an empty list to hold the formatted parts
    xpath_parts = []

    # Iterate over each part
    for part in parts:
        # Check if the part contains an attribute
        if '@' in part:
            # Split the part into element and attribute
            element, attribute = part.split("@")
            # Split the attribute into name and value
            attr_name, attr_value = attribute.split(":")
            # Format and append the part to the list
            xpath_parts.append(f"{element}[@{attr_name}='{attr_value}']")
        else:
            # If no attribute, just append the element
            xpath_parts.append(part)

    # Join all parts with '/' to form the final XPath
    xpath = "/".join(xpath_parts)
    return xpath

def modifyInput(root: ET.Element, mod_dict: dict[str, Any]) -> ET.Element:
  """
  Modify the inner workflow XML
  @ In, root, ET.Element, the XML of the inner workflow
  @ In, mod_dict, dict[str, Any], modifications to make to the workflow
  @ Out, root, ET.Element, the modified XML
  """
  # Set sampler limit to the number of denoises
  for k, v in mod_dict.items():
    xpath = alias_to_xpath(k)
    root.find(xpath).text = str(v)
    if "denoises" in xpath and (limit_node := root.find('.//samplerInit/limit')) is not None:  # special handling for denoises
      limit_node.text = str(v)
  return root
