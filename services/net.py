import aiohttp

def new_session():
    return aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
