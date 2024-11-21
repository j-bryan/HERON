import xml.etree.ElementTree as ET
import re

def increment(item, d):
  item = item.strip().rsplit("_", 1)[0] + f"_{d}"
  return item

def modifyInput(root: ET.Element, mod_dict: dict) -> ET.Element:
  # Modify the MonteCarlo sampler (if present) to reflect the desired number of samples and to update the
  # values of constant quantities.
  mc = root.find("Samplers/MonteCarlo")
  if mc is None:
    # No MonteCarlo sampler node, so nothing to update
    return root

  # Set sampler limit to the number of denoises
  denoises = mod_dict["Samplers|MonteCarlo@name:mc_arma_dispatch|constant@name:denoises"]
  mc.find('samplerInit/limit').text = denoises

  # Set the component capacities as constants in the sampler
  pattern = r"(?<=@name:)\w+(?=_capacity)"  # regex pattern for "*@name:{comp_name}_capcity*"
  for k, v in mod_dict.items():
    if match := re.search(pattern, k):
      comp = match.group()
      const = mc.find(f"constant[@name='{comp}_capacity']").text =
      const.text = mod_dict[f"Samplers|MonteCarlo@name:mc_arma_dispatch|constant@name:{comp}_capacity"]

  return root
