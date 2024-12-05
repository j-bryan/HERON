from ..utils import attrib_property
from .base import RavenSnippet


class Database(RavenSnippet):
  snippet_class = "Databases"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    attrib_property(cls, "read_mode", "readMode")
    attrib_property(cls, "directory")
    attrib_property(cls, "filename")

  def __init__(self,
               name: str,
               read_mode: str = "overwrite",
               directory: str = "",
               filename: str = "",
               compression: str = "",
               variables: list[str] = []):
    """
    Database snippet constructor
    @ In, name, str,
    """
    super().__init__(name)
    self.read_mode = read_mode
    self.directory = directory
    # Only setting if a non-empty string is provided makes it so these are optional and do not appear in the XML node
    # attributes if they have not been set.
    if filename:
      self.filename = filename
    if compression:
      self.compression = compression

    # We use a set to keep track of variables to avoid accidentally adding duplicate variable names and because
    # the order of variables doesn't matter here.
    self.variables = set(variables)

  #####################
  # Getters & Setters #
  #####################
  def add_variable(self, *vars: str):
    self.variables.update(vars)


class NetCDF(Database):
  tag = "NetCDF"


class HDF5(Database):
  tag = "HDF5"

  @classmethod
  def _create_accessors(cls):
    super()._create_accessors()
    attrib_property(cls, "compression")
