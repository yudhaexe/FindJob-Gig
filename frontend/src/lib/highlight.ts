// Highlight the words of a search query (DESIGN-UIUX.md §2.3 Description tab).
import { createElement, type ReactNode } from "react";

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Positive terms of a query (`-x` excluded, quotes and trailing `*` dropped) as one regex, or null. */
export function termsRegex(q: string): RegExp | null {
  const parts: string[] = [];
  for (const m of q.matchAll(/(-?)"([^"]+)"|(-?)(\S+)/g)) {
    if (m[1] || m[3]) continue;
    const raw = (m[2] ?? m[4] ?? "").trim();
    const prefix = raw.endsWith("*");
    const word = raw.replace(/\*+$/, "");
    if (word.length < 2) continue;
    // Same rules as the search: word start, simple plural, prefix match for `x*`.
    parts.push(`\\b${escape(word)}${prefix ? "\\w*" : "(?:e?s)?\\b"}`);
  }
  if (!parts.length) return null;
  parts.sort((a, b) => b.length - a.length); // longest first so phrases win over their words
  return new RegExp(`(${parts.join("|")})`, "gi");
}

/** Split text into strings and <mark> elements. */
export function highlightText(text: string, re: RegExp | null): ReactNode[] {
  if (!re) return [text];
  return text.split(re).map((part, i) => (i % 2 ? createElement("mark", { key: i }, part) : part));
}

/** Wrap matches inside the text nodes of an (already sanitized) DOM tree. */
export function highlightDom(root: Node, re: RegExp | null): void {
  if (!re) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  for (const node of nodes) {
    const parts = (node.nodeValue ?? "").split(re);
    if (parts.length < 2) continue;
    const frag = document.createDocumentFragment();
    parts.forEach((part, i) => {
      if (!part) return;
      if (i % 2) {
        const mark = document.createElement("mark");
        mark.textContent = part;
        frag.appendChild(mark);
      } else frag.appendChild(document.createTextNode(part));
    });
    node.replaceWith(frag);
  }
}
