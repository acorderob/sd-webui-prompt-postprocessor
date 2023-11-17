# Prompt Postprocessor for Stable Diffusion WebUI

(formerly known as "sd-webui-sendtonegative")

Extension for [AUTOMATIC1111 Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui). Compatible with [SD.Next](https://github.com/vladmandic/automatic).

## Purpose

The purpose of this extension is to process the prompt after other extensions have possibly modified it.

Currently this extension allows the tagging of parts of the prompt and moves them to the
negative prompt. This allows useful tricks when using a wildcard extension
since you can add negative content from choices made in the positive prompt.

Note: The extension must be loaded after the installed wildcards extension. Extensions
load by their folder name in alphanumeric order.

With the ["Dynamic Prompts" extension](https://github.com/adieyal/sd-dynamic-prompts)
this happens by default due to default folder names for both extensions. But if
this is not the case, you can just rename this extension's folder so the ordering
works out.

With the ["AUTOMATIC1111 Wildcards" extension](https://github.com/AUTOMATIC1111/stable-diffusion-webui-wildcards)
you will have to rename one of the folders, so that it loads before than this extension.

When in doubt, just rename this extension's folder with a "z" in front (for example) so that it is the last one to load, or manually set such folder name when installing it.

Note: it only recognizes regular A1111 prompt formats. So:

* Attention: \[prompt\] (prompt) (prompt:weight)
* Alternation: \[prompt1|prompt2|...\]
* Scheduling: \[prompt1:prompt2:step\]

In SD.Next that means only the A1111 or Full parsers.

It does not build equivalent AND/BREAK separations into the negative prompt.

## Installation

1. Go to Extensions > Install from URL
2. Paste <https://github.com/acorderob/sd-webui-prompt-postprocessor> in the URL for extension's git repository text field
3. Click the Install button
4. Restart the webui

## Usage

### Sending content to the negative prompt

The format of the tags is like this:

```text
<!content!>
```

And an optional position in the negative prompt can be specified like this:

```text
<!!position!content!>
```

Where position can be:

* s: at the start (the default)
* e: at the end
* pN: at the position of the insertion point "<!!iN!!>" with N being 0-9

If the insertion point is not found it inserts at the start.

#### Example

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

## Configuration

Separator used when adding to the negative prompt: You can specify the separator used when adding to the negative prompt (by default it's ", ").

Ignore tags with repeated content: by default it ignores repeated content to avoid repetitions in the negative prompt.

Join attention modifiers (weights) when possible: by default it joins attention modifiers when possible (joins into one, multipliying their values).

Try to clean-up the prompt after processing: by default cleans up the positive prompt after processing, removing extra spaces and separators.

## Notes

The content of the negative tags is not processed and is copied as-is to the negative prompt. Other modifiers around the tags are processed in the following way.

### Attention modifiers (weights)

They will be translated to the negative prompt. For example:

* `(red<!square!>:1.5)` will end up as `(square:1.5)` in the negative prompt
* `(red[<!square!>]:1.5)` will end up as `(square:1.35)` in the negative prompt (weight=1.5*0.9)
* However `(red<![square]!>:1.5)` will end up as `([square]:1.5)` in the negative prompt. The content of the negative tag is copied as is, and not joined with the surrounding modifier.

### Prompt editing constructs (alternation and scheduling)

Negative tags inside such constructs will copy the construct to the negative prompt, but separating its elements. For example:

* Alternation: `[red<!square!>|blue<!circle!>]` will end up as `[square|], [|circle]` in the negative prompt, instead of `[square|circle]`
* Scheduling: `[red<!square!>:blue<!circle!>:0.5]` will end up as `[square::0.5], [:circle:0.5]` instead of `[square:circle:0.5]`

This should still work as intended, and the only negative point i see is the unnecessary separators.

## License

MIT

## Contact

If you have any questions or concerns, please leave an issue, or start a thread in the discussions.
