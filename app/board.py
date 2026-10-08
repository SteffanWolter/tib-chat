"""Live boards: what an agent just said in a call, restructured into cards next to the video.

the llm writes SpecStream (json-render's format, github.com/vercel-labs/json-render): JSONL, one RFC 6902 patch
per line. the browser applies every finished line, so cards appear while the model is still writing.
the model only restructures. it is told not to add a single fact.
"""
import config
import llm

# every name checked against lucide-static 1.52.0 on jsdelivr. the browser falls back to 'sparkles'
ICONS = ['heart-pulse', 'heart', 'pill', 'pill-bottle', 'activity', 'droplet', 'droplets', 'shield-alert', 'shield-check',
         'stethoscope', 'syringe', 'thermometer', 'brain', 'scale', 'apple', 'dumbbell', 'footprints', 'moon', 'cigarette-off',
         'wine-off', 'salad', 'clock', 'calendar', 'triangle-alert', 'info', 'circle-check', 'circle-x', 'ban', 'hospital',
         'microscope', 'flask-conical', 'dna', 'test-tube', 'bed-double', 'siren', 'zap', 'gauge', 'trending-up', 'trending-down',
         'list-checks', 'book-open', 'file-text', 'network', 'search', 'sparkles', 'user', 'users', 'baby', 'leaf', 'utensils',
         'bike', 'timer', 'hand-heart', 'bandage', 'ambulance']

SYSTEM = (
  "You turn what a medical video assistant just said into a small visual board shown next to the video. "
  "Output ONLY JSONL: one RFC 6902 JSON Patch operation per line, nothing else (no prose, no code fences).\n"
  "The UI spec is {\"root\": string, \"elements\": {key: {\"type\": string, \"props\": object, \"children\": [keys]}}}.\n"
  "Line 1: {\"op\":\"add\",\"path\":\"/root\",\"value\":\"board\"}\n"
  "Line 2: {\"op\":\"add\",\"path\":\"/elements/board\",\"value\":{\"type\":\"Board\",\"props\":{\"title\":\"...\"},\"children\":[]}}\n"
  "Then for each item two lines: add the element, then append its key, e.g.\n"
  "{\"op\":\"add\",\"path\":\"/elements/p1\",\"value\":{\"type\":\"Point\",\"props\":{...},\"children\":[]}}\n"
  "{\"op\":\"add\",\"path\":\"/elements/board/children/-\",\"value\":\"p1\"}\n"
  "Components (props):\n"
  "- Board {title: max 6 words}\n"
  "- Point {icon, title: max 6 words, text: max 18 words}  one key point; use one Point per item of an enumeration (first, second, third)\n"
  "- Stat {icon, value: very short, e.g. \"Class I\", \"Level A\", \"< 140 mmHg\", \"2 weeks\", label: max 5 words}\n"
  "- Warning {icon, text: max 20 words}  cautions, contraindications, side effects, emergencies\n"
  "- Chips {label: max 4 words, items: up to 6 short strings}\n"
  f"icon must be one of: {', '.join(ICONS)}. Pick the icon that best fits each item.\n"
  "Rules: 2 to 5 children under the board. Use only what the text says, in its own words: never add facts, numbers, "
  "mechanisms or explanations that are not in the text, and never complete a sentence the speaker did not say. "
  "Write in the language of the text. If the text is only small talk with no content, output just the two Board lines with a fitting title "
  "and one Point summarising it."
)


def board(text):
  if not config.LLM_API_KEY:
    yield {'type': 'error', 'message': 'not configured'}
    return
  try:
    for kind, val in llm.stream([{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': str(text)[:2500]}]):
      if kind == 'text':
        yield {'type': 'delta', 'text': val}
    yield {'type': 'done'}
  except Exception as e:
    yield llm.error_event(e)
