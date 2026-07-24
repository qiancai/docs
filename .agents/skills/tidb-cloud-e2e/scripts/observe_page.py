# Filtered accessibility-tree observation for Browser Use CLI.
# Usage:
#   BU_CDP_URL=http://127.0.0.1:9222 browser-use < observe_page.py [URL]
# Prints one "role \"name\"" line per meaningful element (~5 KB/page instead of
# the ~12 KB full snapshot). Runs entirely inside the browser-use daemon;
# only this compact listing reaches the agent.

import sys

INTERESTING = {
    "button", "textbox", "combobox", "checkbox", "radio", "link", "heading",
    "dialog", "switch", "menuitem", "tab", "searchbox", "slider", "listbox",
    "option", "radiogroup", "region", "main", "navigation", "alert",
    "StaticText", "paragraph",
}


def observe():
    tree = cdp("Accessibility.getFullAXTree")["nodes"]  # noqa: F821 (helper injected by browser-use)
    lines = []
    for n in tree:
        if n.get("ignored"):
            continue
        role = (n.get("role", {}).get("value") or "").strip()
        if role not in INTERESTING:
            continue
        name = (n.get("name", {}).get("value") or "").strip()
        lines.append(f'{role} "{name}"' if name else role)
    return lines


ensure_real_tab()  # noqa: F821
if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
    goto_url(sys.argv[1])  # noqa: F821
    wait_for_load()  # noqa: F821
    wait(3)  # noqa: F821

lines = observe()
print("\n".join(lines))
print(f"---\n{len(lines)} lines")
