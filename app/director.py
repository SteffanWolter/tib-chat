"""The director of Guido's shared screen. Cloudflare Workers AI, @cf/cloudflare/clef-flash.

clef-flash is not a chat model. it's a 9B decision model: you give it a state and typed questions
(noul = yes/no, choice, score) and it returns a probability for every allowed answer in one forward pass.
about 0.4 s from Germany. the browser only moves a window when the probability is high enough.
model card: huggingface.co/Cloudflare/clef-flash
"""
import json
import urllib.error
import urllib.request

import config

URL = 'https://api.cloudflare.com/client/v4/accounts/{}/ai/run/@cf/cloudflare/clef-flash'
WINDOWS = {
  'graph': 'the knowledge graph window: the live traversal from the question to concepts and recommendations',
  'table': 'the guideline window: the original guideline table and page with the cited recommendation highlighted',
  'inspector': 'the concept inspector: UMLS and Wikidata facts about one drug or condition (interactions, uses, targets, identifiers)',
  'notes': 'the notes window: a short visual summary of the points the speaker is making',
}
STATE_KEYS = ('phase', 'speaker', 'utterance', 'question', 'open_windows', 'front_window', 'concepts', 'recommendations')


def questions(concepts):
  q = {
    'front': {'type': 'choice', 'instructions': 'Which window on the shared screen best supports what is happening or being said right now?',
              'criteria': WINDOWS},
    'show_table': {'type': 'noul', 'instructions': 'Is the speaker referring to a specific guideline recommendation, its class or level of evidence, or the guideline text?'},
    'show_inspector': {'type': 'noul', 'instructions': 'Is the speaker talking about a specific drug, substance or condition whose facts (interactions, side effects, uses) would help?'},
    'layout': {'type': 'choice', 'instructions': 'How should the open windows be arranged so the viewer can follow?',
               'criteria': {'focus': 'one large window in front, others small', 'split': 'two windows side by side', 'grid': 'all windows visible at once'}},
  }
  if len(concepts) >= 2:  # choice needs at least two options
    q['concept'] = {'type': 'choice', 'instructions': 'Which of these concepts is the speaker mainly talking about?',
                    'criteria': {f'c{i}': c for i, c in enumerate(concepts)}}
  return q


def decide(state):
  if not (config.CF_ACCOUNT_ID and config.CF_API_TOKEN):
    return {'error': 'director not configured'}
  concepts = [str(c)[:60] for c in (state.get('concepts') or [])][:12]
  body = {'model': 'clef-flash', 'state': {k: state[k] for k in STATE_KEYS if state.get(k) is not None}, 'questions': questions(concepts)}
  req = urllib.request.Request(URL.format(config.CF_ACCOUNT_ID), data=json.dumps(body).encode(), method='POST',
                               headers={'Authorization': 'Bearer ' + config.CF_API_TOKEN, 'Content-Type': 'application/json'})
  try:
    with urllib.request.urlopen(req, timeout=6) as r:
      res = json.load(r).get('result', {})
  except urllib.error.HTTPError as e:
    return {'error': f'clef-flash HTTP {e.code}'}
  except Exception as e:
    return {'error': type(e).__name__}
  answers = res.get('answers', {})
  out = {'model': res.get('model'), 'answers': answers}
  if answers.get('concept', {}).get('choice'):
    out['concept_label'] = concepts[int(answers['concept']['choice'][1:])]
  return out
