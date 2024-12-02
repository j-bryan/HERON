import xml.etree.ElementTree as ET

# from .base import RavenSnippet
from .steps import Step
from ..xml_utils import find_node


class Sequence(ET.Element):
  def __init__(self) -> None:
    super().__init__("Sequence")
    # TODO: Storing Step objects instead of just their names could let us dynamically decide the order of steps by
    # looking at step inputs and outputs.
    self._steps = []  # list[str]

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

class RunInfo(ET.Element):
  def __init__(self) -> None:
    super().__init__("RunInfo")
    # Save required nodes as attributes for easy access
    # The ugly naming convention helps to access the attributes from the node names. These names are
    # hidden to external code, with access provided through properties with pythonic names.
    self._JobName = ET.SubElement(self, "JobName")
    self._WorkingDir = ET.SubElement(self, "WorkingDir")
    self._WorkingDir.text = "."
    self._Sequence = Sequence()
    self.append(self._Sequence)
    self._batchSize = ET.SubElement(self, "batchSize")
    self._batchSize.text = 1

  @classmethod
  def from_xml(cls, node: ET.Element) -> "RunInfo":
    """
    Alternative constructor to instantiate from existing XML
    @ In, node, ET.Element, the template XML
    @ Out, run_info, RunInfo, new RunInfo block object
    """
    run_info = RunInfo()
    # Set RunInfo object values based on existing XML
    for sub in node:
      if sub.tag == "Sequence":
        if not sub.text:
          continue
        for step_name in sub.text.split(","):
          run_info.add_step_to_sequence(step_name.strip())
      elif hasattr(run_info, f"_{sub.tag}"):
        attr = getattr(run_info, f"_{sub.tag}")
        attr.attrib = sub.attrib
        attr.text = sub.text
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
    self._Sequence.add_step(step)

  # Properties and accessors
  @property
  def job_name(self) -> str:
    return self._JobName.text

  @job_name.setter
  def job_name(self, val: str) -> None:
    self._JobName.text = val

  @property
  def working_dir(self) -> str:
    return self._WorkingDir.text

  @working_dir.setter
  def working_dir(self, val: str) -> None:
    self._WorkingDir.text = val

  @property
  def batch_size(self) -> str:
    return self._batchSize.text

  @batch_size.setter
  def batch_size(self, val: str) -> None:
    self._batchSize.text = val

  @property
  def internal_parallel(self) -> bool:
    node = self.find("internalParallel")
    return False if node is None else node.text

  @internal_parallel.setter
  def internal_parallel(self, val: bool) -> None:
    node = find_node(self, "internalParallel")
    node.text = val

  @property
  def num_mpi(self) -> int:
    node = self.find("NumMPI")
    return False if node is None else node.text

  @num_mpi.setter
  def num_mpi(self, val: int) -> None:
    node = find_node(self, "NumMPI")
    node.text = val
