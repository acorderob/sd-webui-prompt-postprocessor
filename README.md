# Prompt Postprocessor for Stable Diffusion WebUI

The Prompt Postprocessor for Stable Diffusion WebUI, formerly known as "sd-webui-sendtonegative", is an extension designed to process the prompt after other extensions have potentially modified it. This extension is compatible with the [AUTOMATIC1111 Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) and [SD.Next](https://github.com/vladmandic/automatic).

Currently this extension has these functions:

* Allows the tagging of parts of the prompt and moves them to the negative prompt. This allows for useful tricks when using a wildcard extension since you can add negative content from choices made in the positive prompt.
* Detect invalid wildcards and act on them.
* Clean up the prompt and negative prompt.

Note: The extension must be loaded after the installed wildcards extension (or any other that modifies the prompt or has it's own syntax expressions). Extensions load by their folder name in alphanumeric order.

With the ["Dynamic Prompts" extension](https://github.com/adieyal/sd-dynamic-prompts) this happens by default due to default folder names for both extensions. But if this is not the case, you can just rename this extension's folder so the ordering works out.

With the ["AUTOMATIC1111 Wildcards" extension](https://github.com/AUTOMATIC1111/stable-diffusion-webui-wildcards) you will have to rename one of the folders, so that it loads before than this extension.

When in doubt, just rename this extension's folder with a "z" in front (for example) so that it is the last one to load, or manually set such folder name when installing it.

Notes:

1. It only recognizes regular A1111 prompt formats. So:

    * **Attention**: \[prompt\] (prompt) (prompt:weight)
    * **Alternation**: \[prompt1|prompt2|...\]
    * **Scheduling**: \[prompt1:prompt2:step\]
    * **Extra networks**: \<kind:model...\>
    * **BREAK**: prompt1 BREAK prompt2
    * **Composable Diffusion**: prompt1 AND prompt2

    In SD.Next that means only the *A1111* or *Full* parsers. It will warn you if you use the *Compel* parser.
2. It only recognizes wildcards in the *\_\_wildcard\_\_* and *{choice|choice}* formats.
3. Since it should run after other extensions that apply to the prompt, the content should have already been processed by them and there should't be any non recognized syntax anymore.
4. It does not create *AND/BREAK* constructs when moving content to the negative prompt.

## Installation

1. Go to Extensions > Install from URL
2. Paste <https://github.com/acorderob/sd-webui-prompt-postprocessor> in the URL for extension's git repository text field
3. Click the Install button
4. Restart the webui

## Usage

### Detection of remaining wildcards

This extension should run after any wildcard extensions, so any remaining wildcards present in the prompt or negative_prompt at this point of processing must be invalid. Usually you might not notice this problem until you check the image metadata, so this option gives you some ways to detect and treat the problem.

If you choose to not ignore wildcards, the extension will look for any *\_\_wildcard\_\_* or *{choice|choice}* constructs and act as configured.

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

* **s**: at the start (the default)
* **e**: at the end
* **pN**: at the position of the insertion point "**<!!iN!!>**" with N being 0-9

The insertion point of course must be in the negative prompt. If the insertion point is not found it inserts at the start.

#### Example

You have a wildcard for hair colors (\_\_haircolors\_\_) with one being strawberry blonde, but you don't want strawberries. So in that option you add a tag to add to the negative prompt, like so:

```text
blonde
strawberry blonde <!strawberry!>
brunette
```

Then, if that option is chosen this extension will process it later and move that part to the negative prompt.

## Configuration

### General settings

* **Debug**: writes debugging information to the console.
* **What to do with remaining wildcards?**: select what do you want to do with any found wildcards.
  * **Ignore**: do not try to detect wildcards.
  * **Remove**: detect wildcards and remove them.
  * **Add visible warning**: detect wildcards and add a warning text to the prompt, that hopefully produces a noticeable generation.
  * **Stop the generation**: detect wildcards and stop the generation.

### Send to negative prompt settings

* **Apply in img2img**: check if you want to do this processing in img2img processes.
* **Separator used when adding to the negative prompt**: you can specify the separator used when adding to the negative prompt (by default it's ", ").
* **Ignore tags with repeated content**: it ignores repeated content to avoid repetitions in the negative prompt.
* **Join attention modifiers (weights) when possible**: it joins attention modifiers when possible (joins into one, multipliying their values).

### Clean up settings

* **Apply in img2img**: check if you want to do this processing in img2img processes.
* **Remove empty constructs**: removes attention/scheduling/alternation constructs when they are invalid.
* **Remove extra separators**: removes unnecessary separators. This applies to the configured separator and regular commas.
* **Clean up around BREAKs**: removes consecutive BREAKs and unnecessary commas and space around them.
* **Clean up around ANDs**: removes consecutive ANDs and unnecessary commas and space around them.
* **Clean up around extra network tags**: removes spaces around them.
* **Remove extra spaces**: removes other unnecessary spaces.

## Notes on negative tags

Positional insertion tags have less priority that start/end tags, so even if they are at the start or end of the negative prompt, they will end up inside any start/end (and default position) tags.

The content of the negative tags is not processed and is copied as-is to the negative prompt. Other modifiers around the tags are processed in the following way.

### Attention modifiers (weights)

They will be translated to the negative prompt. For example:

* `(red<!square!>:1.5)` will end up as `(square:1.5)` in the negative prompt
* `(red[<!square!>]:1.5)` will end up as `(square:1.35)` in the negative prompt (weight=1.5*0.9)
* However `(red<![square]!>:1.5)` will end up as `([square]:1.5)` in the negative prompt. The content of the negative tag is copied as is, and not joined with the surrounding modifier.

### Prompt editing constructs (alternation and scheduling)

Negative tags inside such constructs will copy the construct to the negative prompt, but separating its elements. For example:

* **Alternation**: `[red<!square!>|blue<!circle!>]` will end up as `[square|], [|circle]` in the negative prompt, instead of `[square|circle]`
* **Scheduling**: `[red<!square!>:blue<!circle!>:0.5]` will end up as `[square::0.5], [:circle:0.5]` instead of `[square:circle:0.5]`

This should still work as intended, and the only negative point i see is the unnecessary separators.

## License

MIT

## Contact

If you have any questions or concerns, please leave an issue, or start a thread in the discussions.
