import sys
import os

# Load HERON tools
HERON_LOC = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir]*4))
sys.path.append(HERON_LOC)

from HERON.templates.snippets import RunInfo, Sequence
sys.path.pop()

import pytest
import xml.etree.ElementTree as ET

from test_steps import setup_iostep


class TestRunInfo:
  @pytest.fixture(scope="class")
  def setup_from_xml(self):
    xml = """
    <RunInfo>
      <JobName>test_job_name</JobName>
      <WorkingDir>.</WorkingDir>
      <Sequence>step1, step2</Sequence>
      <batchSize>2</batchSize>
    </RunInfo>
    """
    root = ET.fromstring(xml)
    run_info = RunInfo.from_xml(root)
    return run_info

  @pytest.fixture(scope="class")
  def setup_default(self):
    run_info = RunInfo()
    return run_info

  def test_snippet_class(self, setup_default):
    assert not setup_default.snippet_class

  def test_tag(self, setup_default):
    assert setup_default.tag == "RunInfo"

  def test_from_xml(self, setup_from_xml):
    assert setup_from_xml.job_name == "test_job_name"
    assert setup_from_xml.working_dir == "."
    assert setup_from_xml.batch_size == 2

    sequence = setup_from_xml.find("Sequence")
    assert sequence.text == ["step1", "step2"]

  def test_job_name(self, setup_default):
    job_name = "new_job_name"
    setup_default.job_name = job_name
    assert setup_default.job_name == job_name
    assert setup_default.find("JobName").text == job_name

  def test_working_dir(self, setup_default):
    working_dir = "path/to/dir"
    setup_default.working_dir = working_dir
    assert setup_default.working_dir == working_dir
    assert setup_default.find("WorkingDir").text == working_dir

  def test_batch_size(self, setup_default):
    batch_size = 10
    setup_default.batch_size = batch_size
    assert setup_default.batch_size == batch_size
    assert setup_default.find("batchSize").text == batch_size

  def test_add_step_to_sequence(self, setup_from_xml):
    setup_from_xml.add_step_to_sequence("new_step")
    sequence = setup_from_xml.find("Sequence")
    assert sequence.text == ["step1", "step2", "new_step"]

  def test_set_parallel_run_settings(self, setup_default):
    parallel_info = {
      "memory": "4g",
      "expectedTime": "72:0:0",
      "clusterParameters": "-P nst"
    }
    setup_default.set_parallel_run_settings(parallel_info)

    for k, v in parallel_info.items():
      node = setup_default.find(k)
      assert node is not None
      assert node.text == v


class TestSequence:
  @pytest.fixture(scope="class")
  def setup_from_xml(self):
    xml = "<Sequence>step1, step2</Sequence>"
    root = ET.fromstring(xml)
    sequence = Sequence.from_xml(root)
    return sequence

  @pytest.fixture(scope="class")
  def setup_default(self):
    return Sequence()

  def test_from_xml(self, setup_from_xml):
    assert setup_from_xml.tag == "Sequence"
    assert not setup_from_xml.snippet_class
    assert setup_from_xml._steps == ["step1", "step2"]

  def test_constructor(self, setup_default):
    assert setup_default.tag == "Sequence"
    assert not setup_default.snippet_class
    assert setup_default._steps == []

  def test_add_step(self, setup_default, setup_iostep):
    setup_default.add_step("step2")
    assert setup_default._steps == ["step2"]

    setup_default.add_step("step1", index=0)
    assert setup_default._steps == ["step1", "step2"]

    setup_default.add_step(setup_iostep)
    assert setup_default._steps == ["step1", "step2", setup_iostep.name]

  def test_get_step_index(self, setup_from_xml, setup_iostep):
    assert setup_from_xml.get_step_index("step1") == 0
    assert setup_from_xml.get_step_index("step2") == 1
    setup_from_xml.add_step(setup_iostep)
    assert setup_from_xml.get_step_index(setup_iostep) == 2
