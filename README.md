# Prompt Postprocessor for Stable Diffusion WebUI and ComfyUI

The Prompt Postprocessor, formerly known as "sd-webui-sendtonegative", is an extension designed to process the prompt, possibly after other extensions have modified it. This extension is compatible with:

* [AUTOMATIC1111 Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
* [SD.Next](https://github.com/vladmandic/automatic).
* [Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge)
* [reForge](https://github.com/Panchovix/stable-diffusion-webui-reForge)
* ...and probably other forks
* [ComfyUI](https://github.com/comfyanonymous/ComfyUI)

Currently this extension has these functions:

* Sending parts of the prompt to the negative prompt. This allows for useful tricks when using wildcards since you can add negative content from choices made in the positive prompt.
* Set and modify local variables.
* Filter content based on the loaded SD model or a variable.
* Process wildcards. Compatible with Dynamic Prompts formats. Can also detect invalid wildcards and act as you choose.
* Clean up the prompt and negative prompt.

Note: when used in an A1111 compatible webui, the extension must be loaded after any other extension that modifies the prompt (like another wildcards extension). Usually extensions load by their folder name in alphanumeric order, so if the extensions are not loading in the correct order just rename this extension's folder so the ordering works out. When in doubt, just rename this extension's folder with a "z" in front (for example) so that it is the last one to load, or manually set such folder name when installing it.

Notes:

1. Other than its own commands, it only recognizes regular A1111 prompt formats. So:

    * **Attention**: `\[prompt\] (prompt) (prompt:weight)`
    * **Alternation**: `\[prompt1|prompt2|...\]`
    * **Scheduling**: `\[prompt1:prompt2:step\]`
    * **Extra networks**: `\<kind:model...\>`
    * **BREAK**: `prompt1 BREAK prompt2`
    * **Composable Diffusion**: `prompt1:weight1 AND prompt2:weight2`

    In SD.Next that means only the *A1111* or *Full* parsers. It will warn you if you use the *Compel* parser.
2. It recognizes wildcards in the *\_\_wildcard\_\_* and *{choice|choice}* formats (and anything that [Dynamic Prompts](https://github.com/adieyal/sd-dynamic-prompts) supports).
3. It does not create *AND/BREAK* constructs when moving content to the negative prompt.

## Installation

On A1111 compatible webuis:

1. Go to Extensions > Install from URL
2. Paste <https://github.com/acorderob/sd-webui-prompt-postprocessor> in the URL for extension's git repository text field
3. Click the Install button
4. Restart the webui

On ComfyUI:

1. Go to Manager > Custom Nodes Manager
2. Install through ComfyUI Manager
3. Click Install via Git URL and enter <https://github.com/acorderob/sd-webui-prompt-postprocessor>
4. Restart

## Usage

### Commands

The extension uses a format for its commands similar to an extranetwork, but it has a "ppp:" prefix followed by the command, and then a space and any parameters (if any).

```text
<ppp:command parameters>
```

When a command is associated with any content, it will be between an opening and a closing command:

```text
<ppp:command parameters>content<ppp:/command>
```

For wildcards and choices it uses the formats from the Dynamic Prompts extension, but sometimes with some additional options for more functionality.

### Choices

The generic format is:

```text
{parameters$$opt1::choice1|opt2::choice2|opt3::choice3}
```

Both the construct parameters (up to the '$$') and the individual choice options (up to the '::') are optional.

There is also a format where instead of "parameters$$" you just put the sampler, for compatibility with Dynamic Prompts.

The construct parameters can be written with the following options (all are optional):

* "**~**" or "**@**": sampler (for compatibility with Dynamic Prompts), but only "**~**" (random) is allowed.
* "**r**": means it allows repetition of the choices.
* "**n**" or "**n-m**" or "**n-**" or "**-m**": number or range of choices to select. Allows zero as the start of a range. Default is 1.
* "**$$sep**": separator when multiple choices are selected. Default is set in settings.
* "**$$**": end of the parameters.

The choice options are as follows:

* "**n**": weight of the choice (default 1)
* "**if condition**": filters out the choice if the condition is false (this is an extension to the Dynamic Prompts syntax). Same conditions as in the `if` command.
* "**::**": end of choice options

Whitespace is allowed between parameters.

These are examples of formats you can use to insert a choice construct:

```text
{opt1|5::opt2|3::opt3}             # select 1 choice, two have weights
{3$$opt1|5 if _is_sd1::opt2|opt3}  # select 3 choices, one has a weight and a condition
{2-3$$opt1|opt2|opt3}              # select 2 to 3 choices
{r2-3$$opt1|opt2|opt3}             # select 2 to 3 choices allowing repetition
{2-3$$ / $$opt1|opt2|opt3}         # select 2 to 3 choices with separator " / "
```

Notes:

* The Dynamic Prompts format `{2$$__flavours__}` does not work as expected. It will only output one value. You can write is as `{r2$$__flavours__}` to get two values, but they may repeat since the evaluation of the wildcard is independent of the choices selection.
* Whitespace in the choices is not ignored like in Dynamic Prompts, but will be cleaned up if the appropiate settings are checked.

### Wildcards

The generic format is:

```text
__parameters$$path/to/wildcard(var=value)__
```

The parameters and the setting of a variable are optional. The parameters follow the same format as for the choices. The variable value only applies during the evaluation of the selected choices and is discarded afterward (the variable keeps its original value if there was one).

In the wildcard definition (which supports the text, json and yaml formats), if the first choice follows the format of these parameters, it will be used as default parameters for that wildcard (see examples in the tests folder). The choices of the wildcard follow the same format as in the choices construct. If using the object format for a choice you can use a new "if" property for the condition in addition to the standard "weight" and "text"/"content".

Wildcards can contain just one choice. In json and yaml formats this allows the use of a string value for the keys, rather than an array.

These are examples of formats you can use to insert a wildcard:

```text
__path/wildcard__            # select 1 choice
__3$$path/wildcard__         # select 3 choices
__2-3$$path/wildcard__       # select 2 to 3 choices
__r2-3$$path/wildcard__      # select 2 to 3 choices allowing repetition
__2-3$$ / $$path/wildcard__  # select 2 to 3 choices with separator " / "
__path/wildcard(var=value)__ # select 1 choice using the specified variable value in the evaluation.
```

#### Detection of remaining wildcards

This extension should run after any other wildcard extensions, so if you don't use the internal wildcards processing, any remaining wildcards present in the prompt or negative_prompt at this point must be invalid. Usually you might not notice this problem until you check the image metadata, so this option gives you some ways to detect and treat the problem.

### Set command

This command sets the value of a variable that can be checked later.

The format is:

```text
<ppp:set varname>value<ppp:/set>
<ppp:set varname evaluate>value<ppp:/set>
<ppp:set varname add>value<ppp:/set>
<ppp:set varname evaluate add>value<ppp:/set>
```

The `evaluate` parameter makes it so the value of the variable is evaluated at this moment, instead of when it is used.

With the `add` parameter the value is added to the current value of the variable. It does not force an immediate evaluation of the old nor the added value.

The Dynamic Prompts format also works:

```text
${var=value}
${var=!value}   # immmediate evaluation
```

If also supports the addition as an extension of the Dynamic Prompts format:

```text
${var+=value}
${var+=!value}
```

### Echo command

This command prints the value of a variable.

The format is:

```text
<ppp:echo varname>
<ppp:echo varname>default<ppp:/echo>
```

The Dynamic Prompts format is:

```text
${var}
${var:default}
```

### If command

This command allows you to filter content based on conditions.

The full format is:

```text
<ppp:if condition1>content one<ppp:elif condition2>content two<ppp:else>other content<ppp:/if>
```

The *conditionN* compares a variable with a value or a list of values. The allowed formats are:

```text
[not] variable
[not] variable operation value
variable [not] operation value
[not] variable operation (value1,value2...)
variable [not] operation (value1,value2...)
```

When there is no value it will check if the variable is truthy.

For a simple value the allowed operations are `eq`, `ne`, `gt`, `lt`, `ge`, `le`, `contains` and the value can be a quoted string or an integer.

For a list of values the allowed operations are `contains`, `in` and the value of the variable is checked against all the elements of the list until one matches.

The variable can be one set with the `set` or `add` commands or you can use internal variables like these (names starting with an underscore are reserved):

* `_sd` : the loaded model version (`"sd1"`, `"sd2"`, `"sdxl"`)
* `_sdname` : the loaded model filename (without path)
* `_sdfullname`: the loaded model filename (with path)
* `_is_sd`: true if the loaded model version is any version of SD
* `_is_sd1`: true if the loaded model version is SD 1.x
* `_is_sd2`: true if the loaded model version is SD 2.x
* `_is_sdxl`: true if the loaded model version is SDXL (includes Pony models)
* `_is_ssd`: true if the loaded model version is SSD (Segmind Stable Diffusion 1B). Note that for an SSD model `_is_sdxl` will also be true.
* `_is_sdxl_no_ssd`: true if the loaded model version is SDXL and not an SSD model.
* `_is_pony`: true if the loaded model version is SDXL and a Pony model (based on its filename). Note that for a pony model `_is_sdxl` will also be true.
* `_is_sdxl_no_pony`: true if the loaded model version is SDXL and not a Pony model.
* `_is_sd3`: true if the loaded model version is SD 3.x
* `_is_flux`: true if the loaded model is Flux

Any `elif`s (there can be multiple) and the `else` are optional.

#### Example

(multiline to be easier to read)

```text
<ppp:if _is_sd1><lora:test_sd1> test sd1x
<ppp:elif _sd_pony><lora:test_pony> test pony
<ppp:elif _sd_sdxl><lora:test_sdxl> test sdxl
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

The old format (`<!...!>`) is not supported anymore.

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

* **Debug level**: what to write to the console. Note: in SD.Next debug messages only show if you launch it with the --debug argument.
* **Pony substrings**: list of substrings to detect a Pony model.
* **Apply in img2img**: check if you want to do the processing in img2img processes (does not apply to ComfyUI node).

### Wildcard settings

* **Process wildcards**: you can choose to process them with this extension or use a different one.
* **Wildcards folders**: you can enter multiple folders separated by commas. In ComfyUI you can leave it empty and add a "wildcards" entry in the extra_model_paths.yaml file.
* **What to do with remaining wildcards?**: select what do you want to do with any found wildcards.
  * **Ignore**: do not try to detect wildcards.
  * **Remove**: detect wildcards and remove them.
  * **Add visible warning**: detect wildcards and add a warning text to the prompt, that hopefully produces a noticeable generation.
  * **Stop the generation**: detect wildcards and stop the generation.
* **Default separator used when adding multiple choices**: what do you want to use by default to separate multiple choices when the options allow it (by default it's ", ").
* **Keep the order of selected choices**: if checked, a multiple choice construct will return them in the order they are in the construct.

### Send to negative prompt settings

* **Separator used when adding to the negative prompt**: you can specify the separator used when adding to the negative prompt (by default it's ", ").
* **Ignore repeated content**: it ignores repeated content to avoid repetitions in the negative prompt.
* **Join attention modifiers (weights) when possible**: it joins attention modifiers when possible (joins into one, multipliying their values).

### Clean up settings

* **Remove empty constructs**: removes attention/scheduling/alternation constructs when they are invalid.
* **Remove extra separators**: removes unnecessary separators. This applies to the configured separator and regular commas.
* **Remove additional extra separators**: removes unnecessary separators at start or end of lines. This applies to the configured separator and regular commas.
* **Clean up around BREAKs**: removes consecutive BREAKs and unnecessary commas and space around them.
* **Use EOL instead of Space before BREAKs**: add a newline before BREAKs.
* **Clean up around ANDs**: removes consecutive ANDs and unnecessary commas and space around them.
* **Use EOL instead of Space before ANDs**: add a newline before ANDs.
* **Clean up around extra network tags**: removes spaces around them.
* **Remove extra spaces**: removes other unnecessary spaces.

### Content removal settings

* **Remove extra network tags**: removes all extra network tags.

## License

MIT

## Contact

If you have any questions or concerns, please leave an issue, or start a thread in the discussions.
