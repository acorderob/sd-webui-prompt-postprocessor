# Send To Negative for Stable Diffusion WebUI

## Purpose

This extension allows the marking of parts of the prompt and moves them to the negative prompt. This allows useful tricks when using a wildcard extension since you can add negative parts from choices made in the positive prompt.

The extension must be loaded after the wildcard extension. With the "Dynamic Prompts" extension this happens by default due to default folder names for both extensions.

## Format

The format is like this:

```text
<!content!>
```

And an optional position in the negative prompt can be specified like this:

```text
<!!position!content!>
```

Where position can be:

* s: at the start
* e: at the end
* pN: at the position of the insertion point "<!!iN!!>" with N being 0-9

The default position is the start, and also if the insertion point is not found.
