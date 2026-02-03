#!/usr/bin/python3

import asyncio
import os
from typing import Dict, List, Optional, Set, Tuple

import aiohttp

###############################################################################
# Main Classes
###############################################################################

class Queries:
    """
    Class with functions to query the GitHub GraphQL (v4) API and the REST (v3)
    API. Also includes functions to dynamically generate GraphQL queries.
    """

    def __init__(self, username: str, access_token: str,
                 session: aiohttp.ClientSession, max_connections: int = 10):
        self.username = username or os.getenv("GITHUB_ACTOR")
        if not self.username:
            raise NameError("GitHub username is not defined!")
        self.access_token = access_token
        self.session = session
        self.semaphore = asyncio.Semaphore(max_connections)

    async def query(self, generated_query: str) -> Dict:
        """Make a request to the GraphQL API."""
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

    async def query_rest(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to the REST API with retry logic for 202 status."""
        headers = {"Authorization": f"token {self.access_token}"}
        params = params or {}
        path = path.lstrip("/")

        for _ in range(30):  # Retry loop
            try:
                async with self.semaphore:
                    async with self.session.get(f"https://api.github.com/{path}",
                                                headers=headers,
                                                params=list(params.items())) as r:
                        if r.status == 202:
                            await asyncio.sleep(2)
                            continue
                        if r.status == 200:
                            return await r.json()
                        else:
                            return {}
            except Exception as e:
                print(f"REST query failed: {e}")
                break
        return {}

class Stats(Queries):
    """
    Inherits from Queries to fetch and format GitHub user statistics.
    """
    
    def __init__(self, username: str, access_token: str, session: aiohttp.ClientSession):
        super().__init__(username, access_token, session)

    async def get_user_data(self) -> Dict:
        """Fetches basic user info and repository counts."""
        query_str = f"""
        {{
          user(login: "{self.username}") {{
            name
            repositories(first: 100, ownerAffiliations: OWNER) {{
              totalCount
              nodes {{
                stargazerCount
                forkCount
              }}
            }}
          }}
        }}
        """
        return await self.query(query_str)

    async def to_str(self) -> str:
        """Formats the gathered data into a readable string."""
        data = await self.get_user_data()
        
        if not data or "data" not in data or not data["data"]["user"]:
            return f"Could not retrieve data for user: {self.username}. Check your token and username."

        user = data["data"]["user"]
        repos = user["repositories"]["nodes"]
        total_stars = sum(repo["stargazerCount"] for repo in repos)
        total_repos = user["repositories"]["totalCount"]

        return (
            f"--- GitHub Stats for {self.username} ({user['name'] or 'N/A'}) ---\n"
            f"Total Repositories: {total_repos}\n"
            f"Total Stars Received: {total_stars}\n"
            f"---------------------------------------"
        )

###############################################################################
# Main Function
###############################################################################

async def main() -> None:
    """
    Fetches credentials from environment variables and prints user stats.
    """
    access_token = os.getenv("ACCESS_TOKEN")
    # Using GITHUB_ACTOR as a fallback for the username
    user = os.getenv("GITHUB_ACTOR")

    if not access_token:
        print("Error: ACCESS_TOKEN environment variable is missing.")
        return
    if not user:
        print("Error: GITHUB_ACTOR environment variable is missing.")
        return

    async with aiohttp.ClientSession() as session:
        s = Stats(user, access_token, session)
        print(await s.to_str())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
