import xml.etree.ElementTree as ET

from .base import RavenSnippet
from .steps import Step
from ..utils import find_node, merge_trees
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
  def job_name(self) -> str:
    return self.find("JobName").text

  @job_name.setter
  def job_name(self, value: str) -> None:
    find_node(self, "JobName").text = value

  @property
  def working_dir(self) -> str:
    return self.find("WorkingDir").text

  @working_dir.setter
  def working_dir(self, value: str) -> None:
    find_node(self, "WorkingDir").text = value

  @property
  def batch_size(self) -> int:
    return self.find("batchSize").text

  @batch_size.setter
  def batch_size(self, value: str) -> None:
    find_node(self, "batchSize").text = value

  @property
  def internal_parallel(self) -> bool | None:
    node = self.find("InternalParallel")
    return None if node is None else node.text

  @internal_parallel.setter
  def internal_parallel(self, value: bool) -> None:
    find_node(self, "InternalParallel").text = value

  @property
  def num_mpi(self) -> int | None:
    node = self.find("NumMPI")
    return None if node is None else node.text

  @num_mpi.setter
  def num_mpi(self, value: int) -> None:
    find_node(self, "NumMPI").text = value

  @listproperty
  def sequence(self) -> list[str]:
    node = self.find("Sequence")
    return getattr(node, "text", []) or []

  @sequence.setter
  def sequence(self, value: list[str | Step]) -> None:
    find_node(self, "Sequence").text = value
