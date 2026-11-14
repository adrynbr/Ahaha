"""Arquivo principal para hospedagens de bot (Shard Cloud, Square Cloud, Discloud etc.)."""

import asyncio

from leadhunter.__main__ import main

if __name__ == "__main__":
    asyncio.run(main())
