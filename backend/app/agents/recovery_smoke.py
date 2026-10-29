"""Live M5 demonstration: python -m app.agents.recovery_smoke."""

import asyncio
from app.agents.guild_smoke import smoke


if __name__ == "__main__":
    raise SystemExit(asyncio.run(smoke(recovery=True)))
