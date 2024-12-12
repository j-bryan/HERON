import xml.etree.ElementTree as ET


def is_subtree_matching(snippet: ET.Element, subs: dict[str, str | dict]):
  if set(sub.tag for sub in snippet) != set(subs.keys()):
    return False

  for sub in snippet:
    if isinstance(subs[sub.tag], dict):
      is_subtree_matching(sub, subs[sub.tag])
    elif subs[sub.tag] != sub.text:
      return False

  return True
