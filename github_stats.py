#!/usr/bin/python3
import asyncio
import os
from typing import Dict, List, Optional, Set, Tuple
import aiohttp

class Queries:
    def __init__(self, username: str, access_token: str,
                 session: aiohttp.ClientSession, max_connections: int = 10):
        self.username = username or os.getenv("GITHUB_ACTOR")
        if not self.username:
            raise NameError("GitHub username is not defined!")
        self.access_token = access_token
        self.session = session
        self.semaphore = asyncio.Semaphore(max_connections)

    async def query(self, generated_query: str) -> Dict:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with self.semaphore:
                async with self.session.post("https://api.github.com/graphql",
                                             headers=headers,
                                             json={"query": generated_query}) as r:
                    return await r.json()
        except Exception as e:
            print(f"GraphQL query failed: {e}")
            return {}

class Stats(Queries):
    # Added **kwargs to catch 'exclude_repos', 'ignore_repos', etc.
    def __init__(self, username: str, access_token: str, session: aiohttp.ClientSession, **kwargs):
        super().__init__(username, access_token, session)
        self.exclude_repos = kwargs.get('exclude_repos', set())
        self.include_forks = kwargs.get('include_forks', False)

    async def to_str(self) -> str:
        query_str = f"""
        {{
          user(login: "{self.username}") {{
            name
            repositories(first: 100, ownerAffiliations: OWNER) {{
              nodes {{
                stargazerCount
                isFork
              }}
            }}
          }}
        }}
        """
        data = await self.query(query_str)
        if not data or "data" not in data or not data["data"]["user"]:
            return "Error: Could not fetch user data."
        
        repos = data["data"]["user"]["repositories"]["nodes"]
        # Filter forks if needed
        if not self.include_forks:
            repos = [r for r in repos if not r["isFork"]]
            
        total_stars = sum(r["stargazerCount"] for r in repos)
        return (f"--- GitHub Stats for {self.username} ---\n"
                f"Total Repositories: {len(repos)}\n"
                f"Total Stars Received: {total_stars}\n"
                f"---------------------------------------")

async def main() -> None:
    access_token = os.getenv("ACCESS_TOKEN")
    user = os.getenv("GITHUB_ACTOR")
    if not access_token or not user:
        return
    async with aiohttp.ClientSession() as session:
        s = Stats(user, access_token, session)
        print(await s.to_str())

if __name__ == "__main__":
    asyncio.run(main())
