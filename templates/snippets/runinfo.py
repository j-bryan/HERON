import xml.etree.ElementTree as ET

from .base import RavenSnippet
from .steps import Step
from ..xml_utils import find_node, merge_trees
from ..decorators import listproperty


class RunInfo(RavenSnippet):
  tag = "RunInfo"

  @classmethod
  def from_xml(cls, node: ET.Element) -> "RunInfo":
    run_info = merge_trees(cls(), node)
    sequence = node.find("Sequence")
    if text := getattr(sequence, "text", None):
      steps = [v.strip() for v in text.split(",")]
      run_info.sequence = steps
    return run_info

  def set_parallel_run_settings(self, parallel_run_info: dict) -> None:
    # NOTE: This doesn't handle non-mpi modes like torque or other custom ones
    mode = find_node(self, "mode")
    mode.text = "mpi"
    qsub = find_node(mode, "runQSUB")
    if memory_val := parallel_run_info.pop("memory", None):
      memory = find_node(mode, "memory")
      memory.text = memory_val
    for tag, value in parallel_run_info.items():
      par_info_sub = find_node(self, tag)
      par_info_sub.text = value

  @property
  def job_name(self) -> str | None:
    node = self.find("JobName")
    return getattr(node, "text", None)

  @job_name.setter
  def job_name(self, value: str) -> None:
    find_node(self, "JobName").text = str(value)

  @property
  def working_dir(self) -> str | None:
    node = self.find("WorkingDir")
    return None if node is None or node.text is None else str(node.text)

  @working_dir.setter
  def working_dir(self, value: str) -> None:
    find_node(self, "WorkingDir").text = str(value)

  @property
  def batch_size(self) -> int:
    node = self.find("batchSize")
    return None if node is None else int(getattr(node, "text", 1))

  @batch_size.setter
  def batch_size(self, value: int) -> None:
    find_node(self, "batchSize").text = int(value)

  @property
  def internal_parallel(self) -> bool | None:
    node = self.find("internalParallel")
    return None if node is None else bool(getattr(node, "text", False))

  @internal_parallel.setter
  def internal_parallel(self, value: bool) -> None:
    find_node(self, "internalParallel").text = bool(value)

  @property
  def num_mpi(self) -> int | None:
    node = self.find("NumMPI")
    return None if node is None else int(getattr(node, "text", 1))

  @num_mpi.setter
  def num_mpi(self, value: int) -> None:
    find_node(self, "NumMPI").text = int(value)

  @listproperty
  def sequence(self) -> list[str]:
    node = self.find("Sequence")
    return getattr(node, "text", []) 

  @sequence.setter
  def sequence(self, value: list[str | Step]) -> None:
    find_node(self, "Sequence").text = [str(v).strip() for v in value]
