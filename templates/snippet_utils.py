import xml.etree.ElementTree as ET

from .heron_types import HeronCase, Source
from .snippets.base import RavenSnippet
from .snippets.dataobjects import DataSet
from .snippets.files import File
from .snippets.models import GaussianProcessRegressor, PickledROM
from .snippets.optimizers import GradientDescent, BayesianOptimizer
from .snippets.outstreams import PrintOutStream
from .snippets.steps import IOStep


def load_pickled_rom(source: Source) -> tuple[File, PickledROM, IOStep]:
  """
  Loads a pickled ROM
  @ In, source, Source, the ROM source
  @ Out, file, File, a Files/Input snippet pointing to the ROM file
  @ Out, rom, PickledROM, the model snippet
  @ Out, step, IOStep, a step to load the model
  """
  # Create the Files/Input node for the ROM source file
  file = File(source.name)
  file.path = source._target_file

  # Create ROM snippet
  rom = PickledROM(source.name)
  if source.needs_multiyear is not None:
    rom.add_subelements({"Multicycle" : {"cycles": source.needs_multiyear}})
  if source.limit_interp is not None:
    rom.add_subelements(maxCycles=source.limit_interp)
  if source.eval_mode == 'clustered':
    ET.SubElement(rom, "clusterEvalMode").text = "clustered"

  # Create an IOStep to load the ROMfrom .he file
  step = IOStep(f"read_{source.name}")
  step.append(file.to_assembler_node("Input"))
  step.append(rom.to_assembler_node("Output"))

  return file, rom, step


def print_rom_meta(rom: RavenSnippet) -> tuple[DataSet, PrintOutStream, IOStep]:
  """
  Print the metadata for a ROM, making the DataSet, Print OutStream, and IOStep to accomplish this.
  @ In, rom, RavenSnippet, the ROM to print
  @ Out, dataset, DataSet, the ROM metadata data object
  @ Out, outstream, PrintOutStream, the outstream to print the data object to file
  @ Out, step, IOStep, the step to print the ROM meta
  """
  if rom.snippet_class != "Models":
    raise ValueError("The RavenSnippet class provided is not a Model!")

  # Create the output data object
  dataset = DataSet(f"{rom.name}_meta")

  # Create the outstream for the dataset
  outstream = PrintOutStream(dataset.name)
  outstream.source = dataset

  # create step
  step = IOStep(f"print_{dataset.name}")
  step.append(rom.to_assembler_node("Input"))
  step.append(dataset.to_assembler_node("Output"))
  step.append(outstream.to_assembler_node("Output"))

  return dataset, outstream, step


# def use_gradient_descent(case: HeronCase, name="cap_opt"):
#   optimizer = GradientDescent(name)

#   # Apply any specified optimization settings
#   opt_settings = case.get_optimization_settings()
#   optimizer.set_opt_settings(opt_settings)
#   optimizer.objective = self._get_opt_metric_out_name(case)
