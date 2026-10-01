Public Abyss uses LTUID_V2 and LTOKEN_V2 from the bot environment (operator cookies).
Users need only /login UID and public HoYoLAB Battle Chronicle visibility.
Their own cookies are not required. The operator session must remain valid and is
subject to HoYoLAB access limits. No credentials are embedded in this patch.
The existing design shows returned honours, deployment counts and floor/chamber
stars without team images. Personal cookie-backed reports retain enlarged teams.
Without operator credentials (or if that request fails), the limited Enka summary
remains the fallback. Private chronicles produce an explicit visibility message.
