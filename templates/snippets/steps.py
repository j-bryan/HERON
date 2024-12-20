import xml.etree.ElementTree as ET
from .base import RavenSnippet


class Step(RavenSnippet):
  snippet_class = "Steps"
  _allowed_subs = ["Function", "Input", "Model", "Sampler", "Optimizer", "SolutionExport", "Output"]

  @classmethod
  def from_xml(cls, node: ET.Element) -> "Step":
    # Using the match_text requires the text of the nodes to match (in addition to tag and attributes). This is to make
    # sure similar assembler nodes (e.g. outputting two PointSets)
    return super().from_xml(node, match_text=True)

  def _add_item(self, tag: str, entity: RavenSnippet) -> None:
    if tag not in self._allowed_subs:
      raise ValueError(f"Step type {self.tag} does not accept subelements with tag {tag}. Allowed: {self._allowed_subs}.")

    # Create an Assembler nodefrom .he entity
    # NOTE: The entity snippet must have defined "class" and "name" attributes
    node = entity.to_assembler_node(tag)

    # Is the entity already serving this role in the step? Check so no duplicates are added.
    for sub in self.findall(tag):
      if sub.attrib == node.attrib and sub.text == node.text:
        return

    # Where to insert the node? Let's do it in order to keep things pretty.
    for i, sub in enumerate(self):  # linear search over subelements since there won't be that many
      if self._allowed_subs.index(sub.tag) > self._allowed_subs.index(node.tag):
        self.insert(i, node)
        break
    else:
      self.append(node)

  ############################
  # Add subelement utilities #
  ############################
  def add_function(self, entity: RavenSnippet) -> None:
    self._add_item("Function", entity)

  def add_input(self, entity: RavenSnippet) -> None:
    self._add_item("Input", entity)

  def add_model(self, entity: RavenSnippet) -> None:
    self._add_item("Model", entity)

  def add_sampler(self, entity: RavenSnippet) -> None:
    self._add_item("Sampler", entity)

  def add_optimizer(self, entity: RavenSnippet) -> None:
    self._add_item("Optimizer", entity)

  def add_solution_export(self, entity: RavenSnippet) -> None:
    self._add_item("SolutionExport", entity)

  def add_output(self, entity: RavenSnippet) -> None:
    self._add_item("Output", entity)


class IOStep(Step):
  tag = "IOStep"
  _allowed_subs = ["Input", "Output"]


class MultiRun(Step):
  tag = "MultiRun"


class PostProcess(Step):
  tag = "PostProcess"
  _allowed_subs = ["Input", "Model", "Output"]


# Unused RAVEN steps: SingleRun, RomTrainer
