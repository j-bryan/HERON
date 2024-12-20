from ..xml_utils import find_node
from ..decorators import listproperty
from .base import RavenSnippet


class Database(RavenSnippet):
  snippet_class = "Databases"

  @property
  def read_mode(self) -> str | None:
    return self.get("readMode", None)

  @read_mode.setter
  def read_mode(self, value: str) -> None:
    self.set("readMode", value)

  @property
  def directory(self) -> str | None:
    return self.get("directory", None)

  @directory.setter
  def directory(self, value: str) -> None:
    self.set("directory", value)

  @property
  def filename(self) -> str | None:
    return self.get("filename", None)

  @filename.setter
  def filename(self, value: str) -> None:
    self.set("filename", value)

  @listproperty
  def variables(self) -> list[str]:
    node = self.find("variables")
    return getattr(node, "text", []) 

  @variables.setter
  def variables(self, value: list[str]) -> list[str]:
    find_node(self, "variables").text = value

  #####################
  # Getters & Setters #
  #####################
  def add_variable(self, *vars: str):
    self.variables.update(vars)


class NetCDF(Database):
  tag = "NetCDF"


class HDF5(Database):
  tag = "HDF5"

  @property
  def compression(self) -> str | None:
    return self.get("compression", None)

  @compression.setter
  def compression(self, value: str) -> None:
    self.set("compression", value)
