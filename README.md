# Prompt Postprocessor for Stable Diffusion WebUI

The Prompt Postprocessor for Stable Diffusion WebUI, formerly known as "sd-webui-sendtonegative", is an extension designed to process the prompt after other extensions have potentially modified it. This extension is compatible with the [AUTOMATIC1111 Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) and [SD.Next](https://github.com/vladmandic/automatic).

Currently this extension has these functions:

* Allows marking parts of the prompt and moves them to the negative prompt. This allows for useful tricks when using a wildcard extension since you can add negative content from choices made in the positive prompt.
* Set values to local variables.
* Filter content based on the loaded SD model version or a set variable.
* Detect invalid wildcards and act on them.
* Clean up the prompt and negative prompt.

Note: The extension must be loaded after the installed wildcards extension (or any other that modifies the prompt or has it's own syntax expressions). Extensions load by their folder name in alphanumeric order.

With the ["Dynamic Prompts" extension](https://github.com/adieyal/sd-dynamic-prompts) this happens by default due to default folder names for both extensions. But if this is not the case, you can just rename this extension's folder so the ordering works out.

With the ["AUTOMATIC1111 Wildcards" extension](https://github.com/AUTOMATIC1111/stable-diffusion-webui-wildcards) you will have to rename one of the folders, so that it loads before than this extension.

When in doubt, just rename this extension's folder with a "z" in front (for example) so that it is the last one to load, or manually set such folder name when installing it.

Notes:

1. It only recognizes regular A1111 prompt formats. So:

    * **Attention**: `\[prompt\] (prompt) (prompt:weight)`
    * **Alternation**: `\[prompt1|prompt2|...\]`
    * **Scheduling**: `\[prompt1:prompt2:step\]`
    * **Extra networks**: `\<kind:model...\>`
    * **BREAK**: `prompt1 BREAK prompt2`
    * **Composable Diffusion**: `prompt1 AND prompt2`

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

### Commands

The extension uses now a new format for its commands. The format is similar to an extranetwork, but it has a "ppp:" prefix followed by the command, and then a space and any parameters (if any).

```text
<ppp:command parameters>
```

When a command is associated with any content, it will be between an opening and a closing command:

```text
<ppp:command parameters>content<ppp:/command>
```

The `set` and `if` commands are the first to be processed.

### Set command

This command sets the value of a variable that can be checked later.

The format is:

```text
<ppp:set varname>value<ppp:/set>
```

### Echo command

This command prints the value of a variable.

The format is:

```text
<ppp:echo varname>
```

### If command

This command allows you to filter content based on conditions.

The format is:

```text
<ppp:if condition1>content one<ppp:elif condition2>content two<ppp:else>other content<ppp:/if>
```

The *conditionN* compares a variable with a value. The operation can be `eq`, `ne`, `gt`, `lt`, `ge`, `le` and the value can be a quoted string or an integer.

The variable can be one set with the `set` command or special variables like:

* `_sd` : the loaded model version (`"sd1"`, `"sd2"`, `"sdxl"`)

Any `elif`s (there can be multiple) and the `else` are optional.

#### Example

(multiline to be easier to read)

```text
<ppp:if _sd eq "sd1"><lora:test_sd1> test sd1
<ppp:elif _sd eq "sd2"><lora:test_sd2> test sd2
<ppp:elif _sd eq "sdxl"><lora:test_sdxl> test sdxl
<ppp:else>unknown model
<ppp:/if>
```

Only one of the options will end up in the prompt, depending on the loaded model.

### Sending content to the negative prompt

The new format for this command is like this:

```text
<ppp:stn position>content<ppp:/stn>
```

Where position is optional (defaults to the start) and can be:

* **s**: at the start of the negative prompt
* **e**: at the end of the negative prompt
* **pN**: at the position of the insertion point in the negative prompt with N being 0-9

The format of the insertion point to be used in the negative prompt is:

```text
<ppp:stn iN>
```

If the insertion point is not found it inserts at the start.

#### Example

You have a wildcard for hair colors (\_\_haircolors\_\_) with one being strawberry blonde, but you don't want strawberries. So in that option you add a command to add to the negative prompt, like so:

```text
blonde
strawberry blonde <ppp:stn>strawberry<ppp:/stn>
brunette
```

Then, if that option is chosen this extension will process it later and move that part to the negative prompt.

#### Old format

The old format is still supported (for now) and is like this:

```text
<!content!>
```

And an optional position can be specified like this:

```text
<!!position!content!>
```

With the insertion point like this:

```text
<!!iN!!>
```

### Notes on negative commands

Positional insertion commands have less priority that start/end commands, so even if they are at the start or end of the negative prompt, they will end up inside any start/end (and default position) commands.

The content of the negative commands is not processed and is copied as-is to the negative prompt. Other modifiers around the commands are processed in the following way.

#### Attention modifiers (weights)

They will be translated to the negative prompt. For example:

* `(red<ppp:stn>square<ppp:/stn>:1.5)` will end up as `(square:1.5)` in the negative prompt
* `(red[<ppp:stn>square<ppp:/stn>]:1.5)` will end up as `(square:1.35)` in the negative prompt (weight=1.5*0.9)
* However `(red<ppp:stn>[square]<ppp:/stn>:1.5)` will end up as `([square]:1.5)` in the negative prompt. The content of the negative tag is copied as is, and not joined with the surrounding modifier.

#### Prompt editing constructs (alternation and scheduling)

Negative commands inside such constructs will copy the construct to the negative prompt, but separating its elements. For example:

* **Alternation**: `[red<ppp:stn>square<ppp:/stn>|blue<ppp:stn>circle<ppp:/stn>]` will end up as `[square|], [|circle]` in the negative prompt, instead of `[square|circle]`
* **Scheduling**: `[red<ppp:stn>square<ppp:/stn>:blue<ppp:stn>circle<ppp:/stn>:0.5]` will end up as `[square::0.5], [:circle:0.5]` instead of `[square:circle:0.5]`

This should still work as intended, and the only negative point i see is the unnecessary separators.

## Configuration

### General settings

* **Debug**: writes debugging information to the console.
* **What to do with remaining wildcards?**: select what do you want to do with any found wildcards.
  * **Ignore**: do not try to detect wildcards.
  * **Remove**: detect wildcards and remove them.
  * **Add visible warning**: detect wildcards and add a warning text to the prompt, that hopefully produces a noticeable generation.
  * **Stop the generation**: detect wildcards and stop the generation.

### Content removal settings

* **Remove extra network tags**: removes all extra network tags.

### Send to negative prompt settings

* **Apply in img2img**: check if you want to do this processing in img2img processes.
* **Separator used when adding to the negative prompt**: you can specify the separator used when adding to the negative prompt (by default it's ", ").
* **Ignore repeated content**: it ignores repeated content to avoid repetitions in the negative prompt.
* **Join attention modifiers (weights) when possible**: it joins attention modifiers when possible (joins into one, multipliying their values).

### Clean up settings

* **Apply in img2img**: check if you want to do this processing in img2img processes.
* **Remove empty constructs**: removes attention/scheduling/alternation constructs when they are invalid.
* **Remove extra separators**: removes unnecessary separators. This applies to the configured separator and regular commas.
* **Remove additional extra separators**: removes unnecessary separators at start or end of lines. This applies to the configured separator and regular commas.
* **Clean up around BREAKs**: removes consecutive BREAKs and unnecessary commas and space around them.
* **Clean up around ANDs**: removes consecutive ANDs and unnecessary commas and space around them.
* **Clean up around extra network tags**: removes spaces around them.
* **Remove extra spaces**: removes other unnecessary spaces.

## License

MIT

## Contact

If you have any questions or concerns, please leave an issue, or start a thread in the discussions.
