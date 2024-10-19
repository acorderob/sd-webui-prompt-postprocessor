# Prompt PostProcessor for Stable Diffusion WebUI and ComfyUI

The Prompt PostProcessor (PPP), formerly known as "sd-webui-sendtonegative", is an extension designed to process the prompt, possibly after other extensions have modified it. This extension is compatible with:

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

If the extension runs before others, like Dynamic Prompts, and the "Process wildcards" is enabled, the wildcards will be processed by PPP and those extensions will not get them. If you disable processing the wildcards, and intend another extension to process them, you should keep the "What to do with remaining wildcards?" option as "ignore".

Notes:

1. Other than its own commands, it only recognizes regular A1111 prompt formats. So:

    * **Attention**: `\[prompt\] (prompt) (prompt:weight)`
    * **Alternation**: `\[prompt1|prompt2|...\]`
    * **Scheduling**: `\[prompt1:prompt2:step\]`
    * **Extra networks**: `\<kind:model...\>`
    * **BREAK**: `prompt1 BREAK prompt2`
    * **Composable Diffusion**: `prompt1:weight1 AND prompt2:weight2`

    In SD.Next that means only the *A1111* or *Full* parsers. It will warn you if you use the *Compel* parser.

    Does not recognize tokenizer separators like "TE2:" and "TE3:", so sending to negative prompt from those sections of the prompt will not add them in the corresponding section of the negative prompt.

    ComfyUI only supports natively the attention using parenthesis, so the ones with the braces will be converted. The other constructs are not natively supported but some custom nodes implement them.
2. It recognizes wildcards in the *\_\_wildcard\_\_* and *{choice|choice}* formats (and almost everything that [Dynamic Prompts](https://github.com/adieyal/sd-dynamic-prompts) supports).
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

* "**'identifiers'**": comma separated labels for the choice (optional, quotes can be single or double). Only makes sense inside a wildcard definition. Can be used when specifying the wildcard to select this specific choice. It's case insensitive.
* "**n**": weight of the choice (optional, default 1).
* "**if condition**": filters out the choice if the condition is false (optional; this is an extension to the Dynamic Prompts syntax). Same conditions as in the `if` command.
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
* Whitespace in the choices is not ignored like in Dynamic Prompts, but will be cleaned up if the appropriate settings are checked.

### Wildcards

The generic format is:

```text
__parameters$$wildcard'filter'(var=value)__
```

The parameters, the filter, and the setting of a variable are optional. The parameters follow the same format as for the choices.

The wildcard identifier can contain globbing formatting, to read multiple wildcards and merge their choices. Note that if there are no parameters specified, the globbing will use the ones from the first wildcard that matches and have parameters (sorted by keys), so if you don't want that you might want to specify them. Also note that, unlike with Dynamic Prompts, the wildcard name has to be specified with its full path (unless you use globbing).

The filter can be used to filter specific choices from the wildcard. The filtering works before applying the choice conditions (if any). The surrounding quotes can be single or double. The filter is a comma separated list of an integer (positional choice index) or choice label. You can also compound them with "+". That is, the comma separated items act as an OR and the "+" inside them as an AND. Using labels can simplify the definitions of complex wildcards where you want to have direct access to specific choices on occasion (you don't need to create wildcards for each individual choice). There are some additional formats when using filters. You can specify "^wildcard" as a filter to use the filter of a previous wildcard in the chain. You can start the filter (regular or inherited) with "#" and it will not be applied to the current wildcard choices, but the filter will remain in memory to use by other descendant wildcards. You use "#" and "^" when you want to pass a filter to inner wildcards (see the test files).

The variable value only applies during the evaluation of the selected choices and is discarded afterward (the variable keeps its original value if there was one).

These are examples of formats you can use to insert a wildcard:

```text
__path/wildcard__                  # select 1 choice
__path/wildcard'0'__               # select the first choice
__path/wildcard'label'__           # select the choices with label "label"
__path/wildcard'0,label1,label2'__ # select the first choice and those with labels "label1" or "label2"
__path/wildcard'0,label1+label2'__ # select the first choice and those with both labels "label1" and "label2"
__3$$path/wildcard__               # select 3 choices
__2-3$$path/wildcard__             # select 2 to 3 choices
__r2-3$$path/wildcard__            # select 2 to 3 choices allowing repetition
__2-3$$ / $$path/wildcard__        # select 2 to 3 choices with separator " / "
__path/wildcard(var=value)__       # select 1 choice using the specified variable value in the evaluation.
```

#### Wildcard definitions

A wildcard definition can be:

* A txt file. The wildcard name will be the relative path of the file, without the extension. Each line will be a choice. Lines starting with "#" or empty are ignored. Doesn't support nesting.
* An array or scalar value inside a json or yaml file. The wildcard name includes the relative folder path of the file, without the extension, but also the path of the value inside the file (if there is one). If the file contains a dictionary, the filename part is not used for the wildcard name. Supports nesting by having dictionaries inside dictionaries.

The best format is a yaml file with a dictionary of wildcards inside. An editor supporting yaml syntax is recommended.

In a choice, the content after a "#" is ignored.

If the first choice follows the format of wildcard parameters, it will be used as default parameters for that wildcard (see examples in the tests folder). The choices of the wildcard follow the same format as in the choices construct, or the object format of **Dynamic Prompts** (only in structured files). If using the object format for a choice you can use a new "if" property for the condition, and the "labels" property (an array of strings) in addition to the standard "weight" and "text"/"content".

Wildcard parameters in a json/yaml file can also be in object format, and support two additional properties, prefix and suffix:

```yaml
{ sampler: "~", repeating: false, count: 2, prefix: "prefix-", suffix: "-suffix", separator: "/" }
{ sampler: "~", repeating: false, from: 2, to: 3, prefix: "prefix-", suffix: "-suffix", separator: "/" }
```

The prefix and suffix are added to the result along with the selected choices and separators. They can contain other constructs, but the separator can't.

It is recommended to use the object format for the wildcard parameters and for choices with complex options.

Wildcards can contain just one choice. In json and yaml formats this allows the use of a string value for the keys, rather than an array.

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
${var=!value}   # immediate evaluation
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

* `_model` : the loaded model identifier (`"sd1"`, `"sd2"`, `"sdxl"`, `"sd3"`, `"flux"`, `"auraflow"`). `_sd` also works but is deprecated.
* `_modelname` : the loaded model filename (without path). `_sdname` also works but is deprecated.
* `_modelfullname`: the loaded model filename (with path). `_sdfullname` also works but is deprecated.
* `_modelclass`: the class used for the model. Note that this is dependent on the webui. In A1111 all SD versions use the same class. Can be used for new models that are not supported yet with the `_is_*` variables.
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
* `_is_auraflow`: true if the loaded model is AuraFlow

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
* `(red[<ppp:stn>square<ppp:/stn>]:1.5)` will end up as `(square:1.35)` in the negative prompt (weight=1.5*0.9) if the merge attention option is enabled or `([square]:1.5)` otherwise.
* However `(red<ppp:stn>[square]<ppp:/stn>:1.5)` will end up as `([square]:1.5)` in the negative prompt. The content of the negative tag is copied as is, and is not merged with the surrounding modifier because the insertions happen after the attention merging.

#### Prompt editing constructs (alternation and scheduling)

Negative commands inside such constructs will copy the construct to the negative prompt, but separating its elements. For example:

* **Alternation**: `[red<ppp:stn>square<ppp:/stn>|blue<ppp:stn>circle<ppp:/stn>]` will end up as `[square|], [|circle]` in the negative prompt, instead of `[square|circle]`
* **Scheduling**: `[red<ppp:stn>square<ppp:/stn>:blue<ppp:stn>circle<ppp:/stn>:0.5]` will end up as `[square::0.5], [:circle:0.5]` instead of `[square:circle:0.5]`

This should still work as intended, and the only negative point i see is the unnecessary separators.

## Configuration

### A1111 (and compatible UIs) UI options

* **Force equal seeds**: Changes the image seeds and variation seeds to be equal to the first of the batch. This allows using the same values for all the images in a batch.
* **Unlink seed**: Uses the specified seed for the prompt generation instead of the one from the image.
* **Seed**: The seed to use for the prompt generation. If -1 a random one will be used for each image in the batch. This seed is only used for wildcards and choices.
* **Variable seed**: If the seed is not -1 you can use this to increase it for the other images in the batch.

### ComfyUI specific inputs

* **model**: Connect here the MODEL or a string with the model class name used by ComfyUI. Needed for the model kind system variables.
* **modelname**: Name of the model. Needed for the model name system variables and detection of pony (this also requieres for the model to be SDXL).
* **seed**: Connect here the seed used. By default it is -1 (random).
* **pos_prompt**: Connect here the prompt text, or fill it as a widget.
* **neg_prompt**: Connect here the negative prompt text, or fill it as a widget.

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

### Clean up settings

* **Remove empty constructs**: removes attention/scheduling/alternation constructs when they are invalid.
* **Remove extra separators**: removes unnecessary separators. This applies to the configured separator and regular commas.
* **Remove additional extra separators**: removes unnecessary separators at start or end of lines. This applies to the configured separator and regular commas.
* **Clean up around BREAKs**: removes consecutive BREAKs and unnecessary commas and space around them.
* **Use EOL instead of Space before BREAKs**: add a newline before BREAKs.
* **Clean up around ANDs**: removes consecutive ANDs and unnecessary commas and space around them.
* **Use EOL instead of Space before ANDs**: add a newline before ANDs.
* **Clean up around extra network tags**: removes spaces around them.
* **Merge attention modifiers (weights) when possible**: it merges attention modifiers when possible (merges into one, multiplying their values). Only merges individually nested modifiers.
* **Remove extra spaces**: removes other unnecessary spaces.

Please note that ComfyUI does not support the BREAK and AND constructs, but the related settings are kept in that UI.

### Content removal settings

* **Remove extra network tags**: removes all extra network tags.

## License

MIT

## Contact

If you have any questions or concerns, please leave an issue, or start a thread in the discussions.
