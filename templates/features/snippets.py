"""
Utility functions to build common RAVEN XML snippets

@author: Jacob Bryan (@j-bryan)
@date: 2024-11-08
"""

import xml.etree.ElementTree as ET


class EntityNode(ET.Element):
  def __init__(self, tag: str, name: str, subType: str = "", kwarg_subs: dict[str, str] = {}):
    """
    Create the Element. It's common for these Entities to have a number of subnodes which are
    just tag/text pairs. We facilitate the creation of these subnodes by providing the "kwarg_subs"
    argument.
    """
    attrib = {"name": name}
    if subType:
      attrib["subType"] = subType
    super().__init__(tag, attrib)
    for tag, text in kwarg_subs.items():
      sub = ET.SubElement(self, tag)
      sub.text = text

class AssemblerNode(ET.Element):
  """
  Assembler nodes to go in Steps
  """
  def __init__(self, tag, className, typeName, text):
    attrib = {"class": className,
              "type": typeName}
    super().__init__(tag, attrib)
    self.text = text

  @classmethod
  def from_entity(cls, tag, entity):
    return cls(tag=tag, className=entity.get_class(), typeName=entity.get_type(), text=entity.get_name())

class StepNode(ET.Element):
  """
  Steps to go in <Steps> block
  """
  ASSEMBLER_NAMES = ["Function", "Input", "Model", "Sampler", "Optimizer", "SolutionExport", "Output"]

  def __init__(self, tag: str, name: str, subs: list[AssemblerNode]):
    super().__init__(tag, {"name": name})
    # Add assembler nodes in the right order!
    for assemb_name in self.ASSEMBLER_NAMES:
      for sub in subs:
        if sub.tag == assemb_name:
          self.append(sub)
