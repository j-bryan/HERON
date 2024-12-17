import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import HERON.src._utils as hutils
from HERON.src.Cases import Case
from HERON.src.Components import Component
from HERON.src.Placeholders import Placeholder
sys.path.pop()

from .raven_template import RavenTemplate
from .snippets.variablegroups import VariableGroup

class FlatMultiDispatchTemplate(RavenTemplate):
  """
  A template for RAVEN workflows which fix the system capacities and perform an analysis over samples of uncertainty sources,
  including time series sources and uncertain cashflow parameters. Debug mode is a special case of this template.
  """
  def createWorkflow(self, case: Case, components: list[Component], sources: list[Placeholder]) -> None:
    super().createWorkflow(case, components, sources)

class FlatMultiConfigTemplate(RavenTemplate):
  """
  A template for RAVEN workflows which do not consider uncertainty from sources which affect the system dispatch (one time
  history, no uncertain variable costs for dispatchable components). Many system configurations may be considered.
  """
  def createWorkflow(self, case: Case, components: list[Component], sources: list[Placeholder]) -> None:
    super().createWorkflow(case, components, sources)

  def _create_deterministic_results_vargroup(self, name: str, case: Case, components: list[Component]) -> VariableGroup:
    """
    Collects result metric names for deterministic metrics in a variable group
    @ In, case, Case, HERON case
    @ In, components, list[Component], HERON components
    @ Out, results, VariableGroup, results variable group
    """
    pass
