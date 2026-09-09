import requests

from jbot.tools.registry import tool

HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "jbot-agent"}


def _get(url, params=None):
    response = requests.get(url, params=params, headers=HEADERS, timeout=15)
    if response.status_code == 404:
        return None, {"error": f"Not found: {url}"}
    if response.status_code != 200:
        return None, {"error": f"GitHub API error {response.status_code}"}
    return response.json(), None


@tool
def github_user(username: str):
    """Get public GitHub profile details for a username."""
    data, error = _get(f"https://api.github.com/users/{username}")
    if error:
        return error
    return {
        "name": data.get("login"),
        "display_name": data.get("name"),
        "avatar": data.get("avatar_url"),
        "bio": data.get("bio"),
        "public_repos": data.get("public_repos"),
        "followers": data.get("followers"),
        "following": data.get("following"),
        "url": data.get("html_url"),
        "location": data.get("location"),
        "company": data.get("company"),
    }


@tool
def github_users_repos(username: str):
    """List public repositories owned by a GitHub user."""
    data, error = _get(f"https://api.github.com/users/{username}/repos", params={"per_page": 20, "sort": "updated"})
    if error:
        return error
    if not isinstance(data, list):
        return {"error": "Unexpected GitHub response."}
    return [
        {
            "name": repo.get("name"),
            "description": repo.get("description"),
            "stars": repo.get("stargazers_count"),
            "language": repo.get("language"),
            "url": repo.get("html_url"),
        }
        for repo in data
    ]


@tool
def github_search(query: str, search_type: str = "repositories"):
    """
    Search GitHub for repositories, users, issues, or code.

    Args:
        query: What to search for.
        search_type: One of "repositories", "users", "issues", or "code".
    """
    allowed = {"repositories", "users", "issues", "code"}
    if search_type not in allowed:
        return {"error": f"Invalid search_type. Use one of: {sorted(allowed)}"}
    data, error = _get(f"https://api.github.com/search/{search_type}", params={"q": query, "per_page": 10})
    if error:
        return error
    results = data.get("items", [])
    if search_type == "repositories":
        return [
            {
                "name": repo.get("full_name"),
                "description": repo.get("description"),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count"),
                "url": repo.get("html_url"),
            }
            for repo in results
        ]
    if search_type == "users":
        return [
            {"username": user.get("login"), "avatar": user.get("avatar_url"), "url": user.get("html_url")}
            for user in results
        ]
    if search_type == "issues":
        return [
            {
                "title": issue.get("title"),
                "repository": issue.get("repository_url"),
                "url": issue.get("html_url"),
                "state": issue.get("state"),
            }
            for issue in results
        ]
    return [
        {
            "name": item.get("name"),
            "path": item.get("path"),
            "repository": item.get("repository", {}).get("full_name"),
            "url": item.get("html_url"),
        }
        for item in results
    ]


@tool
def github_followers(username: str):
    """List public followers of a GitHub user."""
    data, error = _get(f"https://api.github.com/users/{username}/followers", params={"per_page": 30})
    if error:
        return error
    if not isinstance(data, list):
        return {"error": "Unexpected GitHub response."}
    return [user.get("login") for user in data]
