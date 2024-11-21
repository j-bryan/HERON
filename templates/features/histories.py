from .base import FeatureCollection


class SyntheticHistory(FeatureCollection):
  def __init__(self):
    super().__init__()
    # ROM source
    # Add to ensemble model?
    self._features = []


class StaticHistory(FeatureCollection):
  pass
