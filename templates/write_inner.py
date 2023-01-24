import xml.etree.ElementTree as ET
import copy

def increment(item,d):
  item = item.strip().rsplit('_',1)[0]+'_{}'.format(d)
  return item

def modifyInput(root,mod_dict):
  Samplers = root.find('Samplers')
  # mc
  mc = Samplers.find('MonteCarlo')
  if mc is not None:
    # get the amount of denoising
    denoises = mod_dict.pop('Samplers|MonteCarlo@name:mc_arma_dispatch|constant@name:denoises')
    mc.find('samplerInit').find('limit').text = str(denoises)

    # Look for variables in Monte Carlo sampler for the other variables
    for k, v in mod_dict.items():
      var_name = k.split(':')[-1]
      sampler_var_node = mc.find(f'.//constant[@name="{var_name}"]')
      if sampler_var_node is not None:
        sampler_var_node.text = str(v)
  
  # hacky solution to set seed value from CSV
  random_seed = mc.find('.//constant[@name="random_seed"]')
  seed_value = random_seed.text.split('.')[0]  # string must be formatted like an int, so drop everything after '.'
  multirun = root.find('.//MultiRun[@name="arma_sampling"]')
  multirun.set('re-seeding', seed_value)
  # NOTE My first attempt used the <seed> tag in the pickledROM, but this does not result in
  ## deterministic behavior for parallel sampling. The new strategy passes a seed to the
  ## MultiRun step and the ROM seeds are set directly there in MultiStep initialization.
  # rom_seed = ET.Element('seed')
  # rom_seed.text = random_seed.text
  # load_rom = root.find('.//ROM[@name="Load"]')
  # load_rom.append(rom_seed)

  return root
