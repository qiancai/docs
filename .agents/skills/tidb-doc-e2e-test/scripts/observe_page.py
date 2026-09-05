# Filtered accessibility-tree observation for Browser Use CLI.
# Usage:
#   BU_CDP_URL=http://127.0.0.1:9222 browser-use < observe_page.py [URL] > page.snap
# Output is compatible with snapdiff.py: one "- role \"name\"" line per element,
# with value="..." for form fields and [checked|disabled|...] state markers.
# Runs inside the browser-use daemon; only this compact listing reaches the agent.

import sys

INTERESTING = {
    "button", "textbox", "combobox", "checkbox", "radio", "link", "heading",
    "dialog", "switch", "menuitem", "tab", "searchbox", "slider", "listbox",
    "option", "radiogroup", "region", "main", "navigation", "alert",
    "spinbutton", "StaticText", "paragraph",
}

VALUE_ROLES = {"textbox", "combobox", "searchbox", "slider", "spinbutton", "option"}

STATE_PROPS = ("checked", "selected", "disabled", "expanded", "pressed",
               "required", "readonly", "invalid")


def _state_suffix(node):
    out = []
    for prop in node.get("properties", []):
        pname = (prop.get("name") or "").lower()
        pval = prop.get("value", {}).get("value")
        if pname in STATE_PROPS and pval in (True, "true"):
            out.append(pname)
    return f" [{'|'.join(out)}]" if out else ""


def ax_tree():
    return cdp("Accessibility.getFullAXTree")["nodes"]  # noqa: F821


def wait_stable(max_rounds=20, interval=0.5):
    """Wait until the AX tree stops changing (SPAs render after load).
    No fixed sleeps: poll node count + content hash until stable."""
    last = None
    for _ in range(max_rounds):
        nodes = ax_tree()
        sig = (len(nodes), hash(tuple(str(n.get("name", {}).get("value", ""))
                                      for n in nodes[:200])))
        if sig == last:
            return
        last = sig
        wait(interval)  # noqa: F821


def observe():
    lines = []
    for n in ax_tree():
        if n.get("ignored"):
            continue
        role = (n.get("role", {}).get("value") or "").strip()
        if role not in INTERESTING:
            continue
        name = (n.get("name", {}).get("value") or "").strip()
        value = str(n.get("value", {}).get("value") or "").strip()
        line = f'- {role} "{name}"' if name else f"- {role}"
        if role in VALUE_ROLES and value and value != name:
            line += f' value="{value}"'
        line += _state_suffix(n)
        lines.append(line)
    return lines


ensure_real_tab()  # noqa: F821
if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
    goto_url(sys.argv[1])  # noqa: F821
    wait_for_load()  # noqa: F821
wait_stable()

lines = observe()
print("\n".join(lines))
print(f"# {len(lines)} lines")
