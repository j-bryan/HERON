import xml.etree.ElementTree as ET

from .base import RavenSnippet
from .steps import Step
from ..utils import find_node, node_property


class Sequence(RavenSnippet):
  tag = "Sequence"

  def __init__(self) -> None:
    super().__init__()
    # TODO: Storing Step objects instead of just their names could let us dynamically decide the order of steps by
    # looking at step inputs and outputs.
    self._steps = []  # list[str]

  @classmethod
  def from_xml(cls, node: ET.Element) -> "Sequence":
    sequence = cls()
    if node.text:
      sequence._steps = [step.strip() for step in node.text.split(",")]
      sequence.text = sequence._steps
    return sequence

  def add_step(self, step: Step | str, index: int | None = None) -> None:
    # Make sure we're not duplicating steps by name
    step_name = step.name if isinstance(step, Step) else str(step)
    if step_name in self._steps:
      raise ValueError(f"A step with name '{step_name}' already exists in the Sequence!")

    if index is None:
      self._steps.append(step_name)
    else:
      self._steps.insert(index, step_name)

    self.text = self._steps

  def get_step_index(self, step: Step | str) -> int | None:
    step_name = step.name if isinstance(step, Step) else str(step)
    try:
      idx = self._steps.index(step_name)
    except ValueError:
      idx = None
    return idx

class RunInfo(RavenSnippet):
  tag = "RunInfo"

  @classmethod
  def _create_accessors(cls):
    """
    A shorthand for creating class properties to get and set node attributes and subnode text
    @ In, None
    @ Out, None
    """
    super()._create_accessors()
    node_property(cls, "job_name", "JobName", default="")
    node_property(cls, "working_dir", "WorkingDir", default="")
    node_property(cls, "batch_size", "batchSize", default=1)
    node_property(cls, "internal_parallel", "internalParallel", default=False)
    node_property(cls, "num_mpi", "NumMPI")

  @classmethod
  def from_xml(cls, node: ET.Element) -> "RunInfo":
    """
    Alternative constructor to instantiate from existing XML
    @ In, node, ET.Element, the template XML
    @ Out, run_info, RunInfo, new RunInfo block object
    """
    run_info = cls()
    # Set RunInfo object values based on existing XML
    for sub in node:
      if sub.tag == "Sequence":
        sequence = Sequence.from_xml(sub)
        run_info.append(sequence)
      else:
        run_info.append(sub)
    return run_info

  def set_parallel_run_settings(self, parallel_run_info: dict) -> None:
    #XXX this doesn't handle non-mpi modes like torque or other custom ones
    mode = find_node(self, "mode")
    mode.text = "mpi"
    qsub = find_node(mode, "runQSUB")
    if memory_val := parallel_run_info.pop("memory", None):
      memory = find_node(mode, "memory")
      memory.text = memory_val
    for tag, value in parallel_run_info.items():
      par_info_sub = find_node(self, tag)
      par_info_sub.text = value

  def add_step_to_sequence(self, step: Step) -> None:
    sequence = self.find("Sequence")
    if sequence is None:
      sequence = Sequence()
      self.append(sequence)
    sequence.add_step(step)
