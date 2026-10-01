"""Public Battle Chronicle using the operator's configured HoYoLAB session."""
import os
import genshin

async def public_challenge(uid,command,previous=False):
    ltuid=os.getenv('LTUID_V2','').strip()
    ltoken=os.getenv('LTOKEN_V2','').strip()
    if not ltuid or not ltoken:
        return None
    client=genshin.Client(cookies={'ltuid_v2':ltuid,'ltoken_v2':ltoken},lang='en-us')
    client.region=genshin.Region.CHINESE if os.getenv('HOYOLAB_REGION','os').lower()=='cn' else genshin.Region.OVERSEAS
    if command in ("abyss", "abyssinfo"):
        return await client.get_spiral_abyss(int(uid),previous=previous)
    if command == "stygian":
        return await client.get_stygian_onslaught(int(uid))
    return await client.get_imaginarium_theater(int(uid))

async def public_abyss(uid,previous=False):
    return await public_challenge(uid,"abyss",previous)

