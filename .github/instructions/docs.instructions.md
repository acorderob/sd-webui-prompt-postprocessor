---
description: "Use when writing or editing documentation, README files, or any markdown content."
applyTo: "**/*.md"
---

# Documentation Formatting

## Software and WebUI Names

All software names, WebUI names, and application names must be written in italic using `*name*` syntax — never plain text, bold, or code spans.

Examples of names that must be italic:
- *ComfyUI*, *Stable Diffusion WebUI*, *Forge*, *reForge*, *SD.Next*, *InvokeAI*, *Fooocus*, *AUTOMATIC1111*
- Any other application, platform, or tool name referenced in the docs

**Correct:**
> This extension is compatible with *ComfyUI* and *Forge*.

**Incorrect:**
> This extension is compatible with ComfyUI and Forge.
> This extension is compatible with **ComfyUI** and `Forge`.

**Exceptions:**

- Names inside code blocks (` ``` ` or `` ` `` ) are exempt — they follow code formatting rules.
- When a software name is the visible text of a hyperlink (e.g., `[ComfyUI](https://...)`), plain text is acceptable.

## Use of github alert blocks

When adding notes, tips, warnings, or important information in the documentation, use GitHub's alert block syntax for better visibility and formatting. The syntax is as follows:
```md
> [!NOTE]
> This is a note.
> [!TIP]
> This is a tip.
> [!IMPORTANT]
> This is important information.
> [!WARNING]
> This is a warning.
> [!CAUTION]
> This is a caution.
```
