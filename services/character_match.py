"""Resolve exact, token, partial and conservative typo matches."""
import re
import unicodedata
from difflib import SequenceMatcher

def normalize(value):
    value=unicodedata.normalize('NFKD',str(value)).casefold()
    return ' '.join(re.findall(r'[a-z0-9]+',value))

def character_matches(characters,query):
    characters=list(characters)
    query=normalize(query)
    exact=[c for c in characters if str(c.id)==query or normalize(c.name)==query]
    if exact:return exact
    if len(query.replace(' ',''))<2:raise ValueError('Enter at least two letters or a character ID.')
    pairs=[(c,normalize(c.name)) for c in characters]
    partial=[c for c,n in pairs if query in n or query.replace(' ','') in n.replace(' ','')]
    if partial:return partial
    if len(query.replace(' ',''))<3:return []
    scored=sorted([(max(SequenceMatcher(None,query,part).ratio() for part in [n]+n.split()),c) for c,n in pairs],key=lambda p:p[0],reverse=True)
    if not scored or scored[0][0]<0.65:return []
    return [c for score,c in scored if score>=0.65 and scored[0][0]-score<0.10]

def match_character(characters,query):
    matches=character_matches(characters,query)
    if len(matches)==1:return matches[0]
    if matches:raise ValueError('Several characters match: '+', '.join(c.name for c in matches)+'. Type more of the name.')
    raise ValueError('No matching character found. Try another part of the name.')
