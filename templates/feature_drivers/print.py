from .feature_driver import FeatureDriver, FeatureCollection


class Print(FeatureDriver):
  def _modify_steps(self, template, case, components, sources):
    # Add IOStep to steps with DataObjects <Input> and OutStreams <Output>
    pass

  def _modify_outstreams(self, template, case, components, sources):
    # Add Print outstream node
    pass

  def _modify_runinfo(self, template, case, components, sources):
    # Add IOStep to sequence
    pass
