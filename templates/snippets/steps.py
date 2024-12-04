import xml.etree.ElementTree as ET
from collections import defaultdict

from .base import RavenSnippet


class Step(RavenSnippet):
  snippet_class = "Steps"

  def __init__(self, name: str) -> None:
    # FIXME: step attribute options not exposed in HERON input
    super().__init__(name)
    self._allowed_subs = ["Function", "Input", "Model", "Sampler", "Optimizer", "SolutionExport", "Output"]

  def _add_item(self, tag: str, entity: RavenSnippet) -> None:
    if tag not in self._allowed_subs:
      raise ValueError(f"Step type {self.tag} does not accept subelements with tag {tag}. Allowed: {self._allowed_subs}.")

    # Create an Assembler node from the entity
    # NOTE: The entity snippet must have defined "class" and "name" attributes
    node = entity.to_assembler_node(tag)
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

  ###################################################################
  # Data object input/output getters for determining order of steps #
  ###################################################################
  def get_inputs(self) -> list[str]:
    inputs = [node.text for node in self if node.tag == "Input"]
    return inputs

  def get_outputs(self) -> list[str]:
    outputs = [node.text for node in self if node.tag in ["Outputs", "SolutionExport"]]
    return outputs


class IOStep(Step):
  tag = "IOStep"

  def __init__(self, name: str) -> None:
    super().__init__(name)
    self._allowed_subs = ["Input", "Output"]


class MultiRun(Step):
  tag = "MultiRun"

  def __init__(self, name: str) -> None:
    super().__init__(name)


class PostProcess(Step):
  tag = "PostProcess"

  def __init__(self, name: str) -> None:
    super().__init__(name)
    self._allowed_subs = ["Input", "Model", "Output"]


# Unused RAVEN steps: SingleRun, RomTrainer
