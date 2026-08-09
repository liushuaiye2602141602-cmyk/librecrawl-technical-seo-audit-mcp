"""Rule 1 robots.txt evidence-contract helpers.

The Rule 1 finding must answer "why was this judged blocked?" with
agent-aware evidence. robots.txt groups are evaluated with the standard
crawler semantics: the group with the most specific matching user-agent
applies, and when groups tie on specificity the last matching group in the
file wins. Only search-relevant agents (Googlebot, Bingbot, and the generic
wildcard baseline) can produce a Rule 1 finding; AI/assistant bot blocks are
intentional site policy and are not search over-blocking evidence.
"""

IMPORTANT_PATHS = ("/", "/wp-admin", "/wp-login.php")

# Search-relevant agents that can trigger a Rule 1 important-path finding.
_SEARCH_AGENT_TOKENS = ("googlebot", "bingbot", "*")


def is_search_agent(agent: str) -> bool:
    """True for Googlebot, Bingbot, or the generic wildcard baseline."""
    normalized = (agent or "").strip().lower()
    if normalized == "*":
        return True
    return normalized.startswith("googlebot") or normalized == "bingbot"


def _normalized_groups(groups: list[dict]) -> list[dict]:
    normalized = []
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        agents = sorted({
            str(agent).strip().lower() for agent in group.get("user_agents") or []
            if str(agent).strip()
        })
        disallow = list(group.get("disallow") or [])
        normalized.append({"agents": agents, "disallow": disallow})
    return normalized


def effective_important_blocks(groups: list[dict]) -> list[dict]:
    """Return evidence for important paths blocked for search-relevant agents.

    For each search agent token, find the effective group (most specific
    user-agent match; ties resolved by the last matching group in file order)
    and collect its important-path disallows. The result is a list of
    ``{"applicable_agents": [...], "blocked_paths": [...]}`` records that can
    be attached to a Rule 1 finding as traceable evidence.
    """
    normalized = _normalized_groups(groups)
    relevant: list[dict] = []
    for agent in _SEARCH_AGENT_TOKENS:
        matches: list[tuple[int, int, dict]] = []
        for index, group in enumerate(normalized):
            group_agents = group["agents"]
            if agent in group_agents or "*" in group_agents:
                specificity = 2 if agent in group_agents else 1
                matches.append((specificity, index, group))
        if not matches:
            continue
        highest_specificity = max(item[0] for item in matches)
        best = [item for item in matches if item[0] == highest_specificity]
        # RFC 9309 tie-break: the last matching group of equal specificity wins.
        effective_group = best[-1][2]
        blocked = list(dict.fromkeys(
            path for path in effective_group["disallow"]
            if path in IMPORTANT_PATHS
        ))
        if blocked:
            applicable = sorted({
                candidate for candidate in effective_group["agents"]
                if is_search_agent(candidate)
            })
            if applicable:
                relevant.append({
                    "applicable_agents": applicable,
                    "blocked_paths": blocked,
                })
    # De-duplicate identical evidence records while preserving order.
    seen = set()
    unique: list[dict] = []
    for item in relevant:
        key = (tuple(item["applicable_agents"]), tuple(item["blocked_paths"]))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
