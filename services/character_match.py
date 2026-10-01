"""Resolve exact, token, partial and conservative typo matches."""
import re
import unicodedata
from difflib import SequenceMatcher

def normalize(value):
    value=unicodedata.normalize('NFKD',str(value)).casefold()
    return ' '.join(re.findall(r'[a-z0-9]+',value))

def match_character(characters,query):
    query=normalize(query)
    if len(query.replace(' ',''))<2:
        raise ValueError('Enter at least two letters of the character name.')
    pairs=[(c,normalize(c.name)) for c in characters]
    exact=[c for c,n in pairs if n==query]
    if len(exact)==1:return exact[0]
    partial=[c for c,n in pairs if query in n or query.replace(' ','') in n.replace(' ','')]
    if len(partial)==1:return partial[0]
    if partial:raise ValueError('Several characters match: '+', '.join(c.name for c in partial)+'. Type more of the name.')
    scored=sorted([(max(SequenceMatcher(None,query,part).ratio() for part in [n]+n.split()),c) for c,n in pairs],key=lambda p:p[0],reverse=True)
    if scored and scored[0][0]>=0.65 and (len(scored)==1 or scored[0][0]-scored[1][0]>=0.10):return scored[0][1]
    raise ValueError('No clear match. '+('Try: '+', '.join(c.name for score,c in scored[:4]) if scored else 'No characters available.'))
