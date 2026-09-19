"""Derive Agent-Skills SKILL.md from catalog rows (no extra columns required)."""
from __future__ import annotations

import json
import re


LOCUS = {
    "Skill": "sdk",
    "Agent": "platform",
    "Cron": "cron",
    "Workflow": "platform",
}

MODES = {
    "Skill": (["text"], ["text"]),
    "Agent": (["text"], ["text"]),
    "Cron": (["schedule"], ["json", "text"]),
    "Workflow": (["text"], ["text"]),
}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "skill"


def _tags(product: dict) -> list[str]:
    raw = product.get("tags") or "[]"
    if isinstance(raw, list):
        return [str(t) for t in raw]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(t) for t in parsed]
    except (TypeError, json.JSONDecodeError):
        pass
    return []


def product_to_manifest(product: dict) -> dict:
    category = product.get("category") or "Skill"
    inputs, outputs = MODES.get(category, (["text"], ["text"]))
    tags = _tags(product)
    return {
        "name": slugify(product.get("name") or "skill"),
        "title": product.get("name") or "skill",
        "description": (product.get("description") or "")[:500],
        "category": category,
        "sub_category": product.get("sub_category") or "",
        "skillbazaar_id": product.get("id"),
        "price_coins": product.get("price") or 0,
        "source": product.get("source_platform") or "",
        "github_url": product.get("github_url") or "",
        "seller_name": product.get("seller_name") or "",
        "tags": tags,
        "input_modes": list(inputs),
        "output_modes": list(outputs),
        "execution_locus": LOCUS.get(category, "sdk"),
        "tools_required": tags[:8],
    }


def product_to_skill_md(product: dict) -> str:
    m = product_to_manifest(product)
    lines = [
        "---",
        f"name: {m['name']}",
        f"description: {_yaml_quote(m['description'] or m['title'])}",
        f"metadata:",
        f"  skillbazaar_id: {m['skillbazaar_id']}",
        f"  category: {m['category']}",
        f"  price_coins: {m['price_coins']}",
        f"  execution_locus: {m['execution_locus']}",
    ]
    if m["source"]:
        lines.append(f"  source: {_yaml_quote(m['source'])}")
    if m["github_url"]:
        lines.append(f"  github_url: {_yaml_quote(m['github_url'])}")
    if m["tags"]:
        tag_list = ", ".join(_yaml_quote(t) for t in m["tags"][:8])
        lines.append(f"  tags: [{tag_list}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {m['title']}")
    lines.append("")
    if m["description"]:
        lines.append(m["description"])
        lines.append("")
    lines.append(f"- Category: {m['category']}")
    lines.append(f"- Price: {m['price_coins']} coins")
    if m["github_url"]:
        lines.append(f"- Source: {m['github_url']}")
    lines.append("")
    return "\n".join(lines)


def _yaml_quote(value: str) -> str:
    text = (value or "").replace("\n", " ").strip()
    if not text:
        return '""'
    if re.search(r'[:#\[\]{}&*!|>%@`]', text) or text[0] in "-'\"?":
        return json.dumps(text, ensure_ascii=False)
    return text


def derive_compat(product: dict) -> list:
    """Derive compat list from product data when compat field is not set.

    Priority: skill_type (from skill_assets) > tags > safe default.
    Returns list of compat strings suitable for JSON serialization.
    """
    # Check if product has skill_type from asset
    skill_type = product.get("skill_type")
    if not skill_type:
        # Try to derive from tags
        tags = _tags(product)
        if "sdk" in tags:
            return ["sdk"]
        elif "code" in tags:
            return ["code"]
        elif "prompt" in tags:
            return ["prompt"]
        else:
            # Safe default
            return ["prompt"]

    # Map skill_type to compat runtime
    type_to_compat = {
        "prompt": ["prompt"],
        "code": ["code"],
        "sdk": ["sdk"],
    }
    return type_to_compat.get(skill_type, ["prompt"])


def compat_to_json(compat_list: list) -> str | None:
    """Serialize compat list to JSON string for DB storage."""
    if not compat_list:
        return None
    return json.dumps(compat_list, ensure_ascii=False)


def parse_skill_manifest(skill_md: str) -> dict:
    """Parse SKILL.md frontmatter and return a dict with extracted fields.

    Extracts: name, description, compat (as list), tags, etc.
    Falls back to empty values if frontmatter is missing or malformed.
    """
    result = {
        "name": "",
        "description": "",
        "compat": [],
        "tags": [],
    }

    # Extract YAML frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---", skill_md, re.DOTALL)
    if not match:
        return result

    frontmatter_text = match.group(1)

    # Extract compat field (supports list format)
    compat_match = re.search(r"^compat:\s*\n((?:\s+-\s+.*\n?)*)", frontmatter_text, re.MULTILINE)
    if compat_match:
        compat_items = re.findall(r"-\s+(.+)", compat_match.group(1))
        result["compat"] = [item.strip().strip('"').strip("'") for item in compat_items]

    # Extract name
    name_match = re.search(r"^name:\s*(.+)", frontmatter_text, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip().strip('"').strip("'")

    # Extract description
    desc_match = re.search(r"^description:\s*(.+)", frontmatter_text, re.MULTILINE)
    if desc_match:
        result["description"] = desc_match.group(1).strip().strip('"').strip("'")

    # Extract tags (list format)
    tags_match = re.search(r"^tags:\s*\n((?:\s+-\s+.*\n?)*)", frontmatter_text, re.MULTILINE)
    if tags_match:
        tag_items = re.findall(r"-\s+(.+)", tags_match.group(1))
        result["tags"] = [item.strip().strip('"').strip("'") for item in tag_items]

    return result
