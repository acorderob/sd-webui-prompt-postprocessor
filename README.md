# Send To Negative for Stable Diffusion WebUI

## Purpose

This extension allows the tagging of parts of the prompt and moves them to the
negative prompt. This allows useful tricks when using a wildcard extension
since you can add negative content from choices made in the positive prompt.

Note: The extension must be loaded after the wildcard extension.

With the "Dynamic Prompts" extension this happens by default due to default
folder names for both extensions. But if this is not the case, you can just
rename the extension folder so the ordering works out.

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

## Example

You have a wildcard for hair colors (\_\_haircolors\_\_) with one being
strawberry blonde, but you don't want strawberries. So in that option you add a
tag to add to the negative prompt, like so:

```text
blonde
strawberry blonde <!strawberry!>
brunette
```

Then, if that option is chosen this extension will process it later and move
that part to the negative prompt.
