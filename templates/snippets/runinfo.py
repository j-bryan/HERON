# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Snippet class for the RunInfo block

  @author: Jacob Bryan (@j-bryan)
  @date: 2024-11-08
"""

from .base import RavenSnippet
from .steps import Step
from ..xml_utils import find_node
from ..decorators import listproperty


class RunInfo(RavenSnippet):
  """ Snippet class for the RAVEN XML RunInfo block """
  tag = "RunInfo"

  # @classmethod
  # def from_xml(cls, node: ET.Element) -> "RunInfo":
  #   run_info = merge_trees(cls(), node)
  #   sequence = node.find("Sequence")
  #   if text := getattr(sequence, "text", None):
  #     steps = [v.strip() for v in text.split(",")]
  #     run_info.sequence = steps
  #   return run_info

  def set_parallel_run_settings(self, parallel_run_info: dict[str, str]) -> None:
    """
    Set how to run in parallel
    @ In, parallel_run_info, dict[str, str], settings for parallel execution
    @ Out, None
    """
    # NOTE: This doesn't handle non-mpi modes like torque or other custom ones
    mode = find_node(self, "mode")
    mode.text = "mpi"
    qsub = find_node(mode, "runQSUB")
    # Handle "memory" setting first since its parent node is the "mode" node
    if memory_val := parallel_run_info.pop("memory", None):
      find_node(mode, "memory").text = memory_val
    # All other settings get tacked onto the main RunInfo block
    for tag, value in parallel_run_info.items():
      find_node(self, tag).text = value

  @property
  def job_name(self) -> str | None:
    """
    Getter for job name
    @ In, None
    @ Out, job_name, str | None, the job name
    """
    node = self.find("JobName")
    return getattr(node, "text", None)

  @job_name.setter
  def job_name(self, value: str) -> None:
    """
    Setter for job name
    @ In, value, str, the job name
    @ Out, None
    """
    find_node(self, "JobName").text = str(value)

  @property
  def working_dir(self) -> str | None:
    """
    Getter for working directory
    @ In, None
    @ Out, working_dir, str | None, the working directory
    """
    node = self.find("WorkingDir")
    return None if node is None or node.text is None else str(node.text)

  @working_dir.setter
  def working_dir(self, value: str) -> None:
    """
    Setter for working directory
    @ In, value, str, the working directory
    @ Out, None
    """
    find_node(self, "WorkingDir").text = str(value)

  @property
  def batch_size(self) -> int:
    """
    Getter for batch size
    @ In, None
    @ Out, batch_size, int | None, the batch size
    """
    node = self.find("batchSize")
    return None if node is None else int(getattr(node, "text", 1))

  @batch_size.setter
  def batch_size(self, value: int) -> None:
    """
    Setter for batch size
    @ In, value, int, the batch size
    @ Out, None
    """
    find_node(self, "batchSize").text = int(value)

  @property
  def internal_parallel(self) -> bool | None:
    """
    Getter for internal parallel flag
    @ In, None
    @ Out, internal_parallel, bool | None, the internal parallel flag
    """
    node = self.find("internalParallel")
    return None if node is None else bool(getattr(node, "text", False))

  @internal_parallel.setter
  def internal_parallel(self, value: bool) -> None:
    """
    Setter for internal parallel flag
    @ In, value, bool, the internal parallel flag
    @ Out, None
    """
    find_node(self, "internalParallel").text = bool(value)

  @property
  def num_mpi(self) -> int | None:
    """
    Getter for number of MPI processes
    @ In, None
    @ Out, num_mpi, int | None, the number of processes
    """
    node = self.find("NumMPI")
    return None if node is None else int(getattr(node, "text", 1))

  @num_mpi.setter
  def num_mpi(self, value: int) -> None:
    """
    Setter for number of MPI processes
    @ In, value, int, the number of MPI processes
    @ Out, None
    """
    find_node(self, "NumMPI").text = int(value)

  @listproperty
  def sequence(self) -> list[str]:
    """
    Getter for the step sequence
    @ In, None
    @ Out, sequence, list[str], list of steps
    """
    node = self.find("Sequence")
    return getattr(node, "text", [])

  @sequence.setter
  def sequence(self, value: list[str | Step]) -> None:
    """
    Setter for the step sequence
    @ In, value, str, the step sequence
    @ Out, None
    """
    find_node(self, "Sequence").text = [str(v).strip() for v in value]
