import xml.etree.ElementTree as ET

from .base import RavenSnippet


class Database(RavenSnippet):
  def __init__(self,
               name: str,
               type_name: str,
               read_mode: str = "overwrite",
               directory: str = "",
               filename: str = "",
               compression: str = "",
               variables: list[str] = []):
    # Input validation
    allowed_types = ["NetCDF", "HDF5"]
    if type_name not in allowed_types:
      raise ValueError(f"Database type must be one of {allowed_types}! Received type {type_name}.")

    super().__init__(name=name, class_name="Databases", type_name="NetCDF")

    # Additional attributes are kept in the self.attrib dict, with values gettable/settable using properties. This
    # implementation allows for control over which attributes are present in self.attrib and validating set values.
    self.attrib = {}
    # directly setting the read_mode and directory properties ensures they are set and will be present in self.attrib
    self.read_mode = read_mode
    self.directory = directory  # empty string is a valid directory
    # Only setting if a non-empty string is provided makes it so these are optional and do not appear in the XML node
    # attributes if they have not been set.
    if filename:
      self.filename = filename
    if compression:
      self.compression = compression

    # We use a set to keep track of variables to avoid accidentally adding duplicate variable names and because
    # the order of variables doesn't matter here.
    self.variables = set(variables)

  def to_xml(self) -> ET.Element:
    # Add variables to settings so Entity.to_xml() will add the <variables> child node
    if self.variables:
      vars = ", ".join(self.variables)
      self.add_subelements(variables=vars)

    # Create node and set additional attributes
    node = super().to_xml()
    node.attrib.update(self.attrib)

    return node

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

  @property
  def compression(self) -> str | None:
    return self.attrib.get("compression", None)

  @compression.setter
  def compression(self, compression: str) -> None:
    # TODO: Is compression setting allowed for NetCDF?
    allowed_values = ["gzip", "lzf"]
    if compression.lower() not in allowed_values:
      raise ValueError(f"Database compression must be one of {allowed_values}. Received '{compression.lower()}'.")
    self.attrib["compression"] = compression.lower()

  def add_variable(self, *vars: str):
    for v in vars:
      self.variables.add(v)
