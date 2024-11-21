import xml.etree.ElementTree as ET
from collections import defaultdict

from .snippets import AssemblerNode
from .base import Feature, Entity
from .entities import Entity, Function, File, DataObject, Database, Model, Sampler, Optimizer, SolutionExport, OutStream


class Step(Feature, Entity):
  def __init__(self,
               name: str,
               step_type: str,
               functions: list[Function] | Function = [],
               inputs: list[File | DataObject] | File | DataObject = [],
               model: Model | None = None,
               sampler: Sampler | None = None,
               optimizer: Optimizer | None = None,
               outputs: list[OutStream | DataObject] | OutStream | DataObject = []):
    super().__init__(name=name, class_name="Steps", type_name=step_type)

    # Possible Step assembler nodes
    # NOTE: There are some requirements for what is a valid RAVEN step, but we won't check that here.
    #       It might be worth adding this in the future, but for now, it's on the developer to set steps
    #       up correctly. The Step child classes should help to automate this for common step types.
    # Sets are used to ensure no duplicate entities of each Assembler node type are present.
    self.entities = defaultdict(set)
    self.add_entities("Function", functions)
    self.add_entities("Input", inputs)
    self.add_entities("Model", model)
    self.add_entities("Sampler", sampler)
    self.add_entities("Optimizer", optimizer)
    self.add_entities("Output", outputs)

    # If an optimizer was given, get the SolutionExport target and add that to the entities dict
    if self.entities["Optimizer"]:
       self.entities["SolutionExport"].add(optimizer.get_export_target())

    # Fix the order in which entities are added to a step
    self._entity_order = ["Function", "Input", "Model", "Sampler", "Optimizer", "Output"]
    # If we add all of the Entities as Assembler nodes to the settings dict as dict(name=node) pairs,
    # the Entity to_xml infrastructure will handle all of the XML building for us.
    self._settings = {}
    for ent_type in self._entity_order:
      for ent in self.entities[ent_type]:
        self._settings[ent.get_name()] = AssemblerNode.from_entity(ent_type, ent)

  def edit_template(self, template, case, components, sources):
    steps = template.find("Steps")
    new_step = ET.SubElement(steps, self.tag)

    # Add assembler nodes to step and populate component XML
    for tag in self._entity_order:
      for ent in self.entities[tag]:
        if not ent:  # Skip over any "None" entries which may have gotten added
          continue
        new_step.append(AssemblerNode.from_entity(tag=tag, entity=ent))
        ent.edit_template(template, case, components, sources)

  def add_entities(self, key: str, entities: Entity | list[Entity] | None):
    if not entities:  # Don't add anything if entities is None or an empty list
      return

    try:
      self.entities[key].update(entities)
    except TypeError:  # entities not iterable
      self.entities[key].add(entities)


class MultiRunStep(Step):
  def __init__(self,
               name: str,
               model: Model,
               sampler: Sampler | None = None,
               optimizer: Optimizer | None = None):
    super().__init__(name=name,
                     step_type="MultiRun",
                     model=model,
                     sampler=sampler,
                     optimizer=optimizer)

    # We need either a sampler or a optimizer
    if sampler and optimizer:  # got both
      raise ValueError("MultiRun received both a Sampler and an Optimizer! Please provide only one or the other.")
    if not (sampler or optimizer):  # got neither
      raise ValueError("MultiRun was not provided a Sampler or an Optimizer! One or the other must be provided.")

    # Step inputs and outputs are the model inputs and outputs
    inputs = model.get_inputs()
    outputs = model.get_outputs()

    if optimizer:
      inputs.extend(optimizer.get_inputs())
      outputs.extend(optimizer.get_outputs())

    self.add_entities("Input", inputs)
    self.add_entities("Output", outputs)


class IOStep(Step):
  """ An IOStep for a single input/output pair """
  def __init__(self, name, inp: DataObject | File, out: OutStream | DataObject | Database):
    super().__init__(name=name,
                     step_type="IOStep",
                     inputs=inp,
                     outputs=out)


class PostProcessStep(Step):
  """ A PostProcess step for a post-processor """
  def __init__(self, name, postprocessor: Model):
    super().__init__(name=name,
                     step_type="PostProcess",
                     inputs=postprocessor.get_inputs(),
                     outputs=postprocessor.get_outputs(),
                     model=postprocessor)
