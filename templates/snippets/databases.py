import xml.etree.ElementTree as ET

from .base import RavenSnippet


class Database(RavenSnippet):
  snippet_class = "Databases"

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
  @property
  def read_mode(self) -> str:
    return self.attrib.get("read_mode")

  @read_mode.setter
  def read_mode(self, read_mode) -> None:
    allowed_values = ["read", "overwrite"]
    if read_mode.lower() not in allowed_values:
      raise ValueError(f"Database read_mode must be one of {allowed_values}. Received '{read_mode.lower()}'.")
    self.attrib["readMode"] = read_mode.lower()

  @property
  def directory(self) -> str:
    return self.attrib.get("directory")

  @directory.setter
  def directory(self, directory: str) -> None:
    # TODO: check if directory exists?
    self.attrib["directory"] = directory

  @property
  def filename(self) -> str:
    return self.attrib.get("filename", f"{self.name}.{'h5' if self.get_type() == 'HDF5' else 'nc'}")

  @filename.setter
  def filename(self, filename: str) -> None:
    self.attrib["filename"] = filename

  def add_variable(self, *vars: str):
    for v in vars:
      self.variables.add(v)


class NetCDF(Database):
  tag = "NetCDF"


class HDF5(Database):
  tag = "HDF5"

  @property
  def compression(self) -> str | None:
    return self.attrib.get("compression", None)

  @compression.setter
  def compression(self, compression: str) -> None:
    allowed_values = ["gzip", "lzf"]
    if compression.lower() not in allowed_values:
      raise ValueError(f"Database compression must be one of {allowed_values}. Received '{compression.lower()}'.")
    self.attrib["compression"] = compression.lower()
