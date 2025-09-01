# Prompt PostProcessor syntax

## Commands

The extension uses a format for its commands similar to an extranetwork, but it has a "ppp:" prefix followed by the command, and then a space and any parameters (if any).

`<ppp:command parameters>`

When a command is associated with any content, it will be between an opening and a closing command:

`<ppp:command parameters>content<ppp:/command>`

For wildcards and choices it uses the formats from the *Dynamic Prompts* extension, but sometimes with some additional options for extra functionality.

## Choices

The generic format is: `{parameters$$opt1::choice1|opt2::choice2|opt3::choice3}`

Both the construct parameters (up to the `$$`) and the individual choice options (up to the '::') are optional.

There is also a format where instead of `parameters$$` you just put the sampler, for compatibility with *Dynamic Prompts*.

The construct parameters can be written with the following options (all are optional):

* "**~**" or "**@**": sampler (for compatibility with *Dynamic Prompts*), but only "**~**" (random) is supported.
* "**r**": means it allows repetition of the choices.
* "**n**" or "**n-m**" or "**n-**" or "**-m**": number or range of choices to select. Allows zero as the start of a range. Default is 1.
* "**$$sep**": separator when multiple choices are selected. Default is set in settings.
* "**$$**": end of the parameters (not optional if any parameters).

The choice options are as follows:

* "**'identifiers'**": comma separated labels for the choice (optional, quotes can be single or double). Only makes sense inside a wildcard definition. Can be used when specifying the wildcard to select this specific choice. It's case insensitive.
* "**n**": weight of the choice (optional, default 1).
* "**if condition**": filters out the choice if the condition is false (optional; this is an extension to the *Dynamic Prompts* syntax). Same conditions as in the `if` command.
* "**::**": end of choice options (not optional if any options)

Whitespace is allowed between parameters/options.

These are examples of formats you can use to insert a choice construct:

| Construct                                      | Result |
| ---------                                      | ------ |
| `{choice1\|5::choice2\|3::choice3}`            | select 1 choice, two of them have weights |
| `{3$$choice1\|5 if _is_sd1::choice2\|choice3}` | select 3 choices, one has a weight and a condition |
| `{2-3$$2::choice1\|choice2\|choice3}`          | select 2 to 3 choices, one of them has a weight |
| `{r2-3$$choice1\|choice2\|choice3}`            | select 2 to 3 choices allowing repetition |
| `{2-3$$ / $$choice1\|choice2\|choice3}`        | select 2 to 3 choices with separator " / " |

Notes:

* The *Dynamic Prompts* format `{2$$__flavours__}` does not work as expected. It will only output one value. You can write is as `{r2$$__flavours__}` to get two values, but they may repeat since the evaluation of the wildcard is independent of the choices selection.
* Whitespace around the choices is not ignored like in *Dynamic Prompts*, but will be cleaned up if the appropriate cleaning settings are selected.

## Wildcards

The generic format is: `__parameters$$wildcard'filter'(var=value)__`

The parameters, the filter, and the setting of a variable are optional. The parameters follow the same format as for the choices.

The wildcard identifier can have a relative path and contain globbing formatting, to read multiple wildcards and merge their choices. Note that if there are no parameters specified, the globbing will use the ones from the first wildcard that matches and have parameters (sorted by keys), so if you don't want that you might want to specify them. Also note that, unlike with *Dynamic Prompts*, the wildcard name has to be specified with its full path (unless you use globbing).

The filter can be used to filter specific choices from the wildcard. The filtering works before applying the choice conditions (if any). The surrounding quotes can be single or double. The filter is a comma separated list of an integer (positional choice index; zero-based) or choice label. You can also compound them with `+`. That is, the comma separated items act as an OR and the `+` inside them as an AND. Using labels can simplify the definitions of complex wildcards where you want to have direct access to specific choices on occasion (you don't need to create wildcards for each individual choice). There are some additional formats when using filters. You can specify `^wildcard` as a filter to use the filter of a previous wildcard in the chain. You can start the filter (regular or inherited) with `#` and it will not be applied to the current wildcard choices, but the filter will remain in memory to use by other descendant wildcards. You use `#` and `^` when you want to pass a filter to inner wildcards (see the test files).

The variable value only applies during the evaluation of the selected choices and is discarded afterward (the variable keeps its original value if there was one).

These are examples of formats you can use to insert a wildcard:

| Construct                            | Result |
| ---------                            | ------ |
| `__wildcard__`                       | select 1 choice |
| `__path/wildcard'0'__`               | select the first choice |
| `__path/wildcard'label'__`           | select the choices with label "label" |
| `__path/wildcard'0,label1,label2'__` | select the first choice and those with labels "label1" or "label2" |
| `__path/wildcard'0,label1+label2'__` | select the first choice and those with both labels "label1" and "label2" |
| `__3$$path/wildcard__`               | select 3 choices |
| `__2-3$$path/wildcard__`             | select 2 to 3 choices |
| `__r2-3$$path/wildcard__`            | select 2 to 3 choices allowing repetition |
| `__2-3$$ / $$path/wildcard__`        | select 2 to 3 choices with separator " / " |
| `__path/wildcard(var=value)__`       | select 1 choice using the specified variable value in the evaluation. |

### Wildcard definitions

A wildcard definition can be:

* A txt file. The wildcard name will be the relative path of the file, without the extension. Each line will be a choice. Lines starting with `#` or empty are ignored. Doesn't support nesting.
* An array or scalar value inside a json or yaml file. The wildcard name includes the relative folder path of the file, without the extension, but also the path of the value inside the file (if there is one). If the file contains a dictionary, the filename part is not used for the wildcard name. Supports nesting by having dictionaries inside dictionaries.

The best format is a yaml file with a dictionary of wildcards inside. An editor supporting yaml syntax and linting is recommended (f.e. vscode).

In a choice, the content after a `#`  is ignored.

If the first choice follows the format of wildcard parameters, it will be used as default parameters for that wildcard (see examples in the tests folder). The choices of the wildcard follow the same format as in the choices construct, or the object format of *Dynamic Prompts* (only in structured files). If using the object format for a choice you can use a new `if` property for the condition, and the `labels` property (an array of strings) in addition to the standard `weight` and `text`/`content`.

```yaml
{ labels: ["some_label"], weight: 2, if: "_is_pony", content: "the text" } # "text" property can be used instead of "content"
```

Wildcard parameters in a json/yaml file can also be in object format, and support two additional properties, prefix and suffix:

```yaml
{ sampler: "~", repeating: false, count: 2, prefix: "prefix-", suffix: "-suffix", separator: "/" }
{ sampler: "~", repeating: false, from: 2, to: 3, prefix: "prefix-", suffix: "-suffix", separator: "/" }
```

The prefix and suffix are added to the result along with the selected choices and separators. They can contain other constructs, but the separator can't.

It is recommended to use the object format for the wildcard parameters and for choices with complex options.

Wildcards can contain just one choice. In json and yaml formats this allows the use of a string value for the keys, rather than an array.

A choice inside a wildcard can also be a list or a dictionary of one element containing a list. These are considered anonymous wildcards. With a list it will be an anonymous wildcard with no choice options, and with a dictionary the key will be the options for the choice containing the anonymous wildcard and the value the choices of the anonymous wildcard. Anonymous wildcards can help formatting complex choice values that are used in only one place and thus creating a regular wildcard is not necessary. See test.yaml for examples.

### Detection of remaining wildcards

This extension should run after any other wildcard extensions, so if you don't use the internal wildcards processing, any remaining wildcards present in the prompt or negative_prompt at this point must be invalid. Usually you might not notice this problem until you check the image metadata, so this option gives you some ways to detect and treat the problem.

## Set command

This command sets the value of a variable that can be checked later.

The format is: `<ppp:set varname [modifiers]>value<ppp:/set>`

These are the available optional modifiers:

* `evaluate`: the value of the variable is evaluated at this moment, instead of when it is used.
* `add`: the value is added to the current value of the variable. It does not force an immediate evaluation of the old nor the added value.
* `ifundefined`: the value will only be set if the variable is undefined.

The `add` and `ifundefined` modifiers are mutually exclusive and cannot be used together.

The *Dynamic Prompts* format also works:

| Construct       | Meaning |
| ---------       | ------- |
| `${var=value}`  | regular evaluation |
| `${var=!value}` | immediate evaluation |

If also supports the addition and undefined check as an extension of the *Dynamic Prompts* format:

| Construct        | Meaning |
| ---------        | ------- |
| `${var+=value}`  | equivalent to "add" |
| `${var+=!value}` | equivalent to "evaluate add" |
| `${var?=value}`  | equivalent to "ifundefined" |
| `${var?=!value}` | equivalent to "evaluate ifundefined" |

## Echo command

This command prints the value of a variable, or the specified default if it doesn't exist.

The format is:

| Construct                              |
| ---------                              |
| `<ppp:echo varname>`                   |
| `<ppp:echo varname>default<ppp:/echo>` |

The *Dynamic Prompts* format is:

| Construct            |
| ---------            |
| `${varname}`         |
| `${varname:default}` |

## If command

This command allows you to filter content based on conditions.

The full format is:

`<ppp:if condition1>content one<ppp:elif condition2>content two<ppp:else>other content<ppp:/if>`

Any `elif`s (there can be multiple) and the `else` are optional.

The `conditionN` can be:

| Construct                                      | Meaning |
| ---------                                      | ------- |
| `variable`                                     | check truthyness of the variable |
| `variable [not] operation value`               | check the variable against a value |
| `variable [not] operation (value1,value2,...)` | check the variable against a list of values |

For a simple value the allowed operations are `eq`, `ne`, `gt`, `lt`, `ge`, `le`, `contains` and the value can be a quoted string or an integer. For a list of values the allowed operations are `contains`, `in` and the value of the variable is checked against all the elements of the list until one matches. The operation can be preceded by `not` for readability, instead of using it in the front.

You can also build complex conditions joining them with boolean operators and/or/not and parentheses.

The variable can be one set with the `set` or `add` commands (user variables) or you can use system variables like these (names starting with an underscore are reserved for system variables):

| System variable    | Value |
| ---------------    | ----- |
| `_model`           | the loaded model identifier (`"sd1"`, `"sd2"`, `"sdxl"`, `"sd3"`, `"flux"`, `"auraflow"`). `_sd` also works but is deprecated. |
| `_modelname`       | the loaded model filename (without path). `_sdname` also works but is deprecated. |
| `_modelfullname`   | the loaded model filename (with path). `_sdfullname` also works but is deprecated. |
| `_modelclass`      | the class used for the model. Note that this is dependent on the webui. In A1111 all SD versions use the same class. Can be used for new models that are not supported yet with the `_is_*` variables. The debug setting will show all system variables when generating in case you need to see which one to use for a certain model. |
| `_is_sd`           | true if the loaded model version is any version of SD |
| `_is_sd1`          | true if the loaded model version is SD 1.x |
| `_is_sd2`          | true if the loaded model version is SD 2.x |
| `_is_sdxl`         | true if the loaded model version is SDXL (includes Pony models) |
| `_is_sd3`          | true if the loaded model version is SD 3.x |
| `_is_flux`         | true if the loaded model is Flux |
| `_is_auraflow`     | true if the loaded model is AuraFlow |
| `_is_ssd`          | true if the loaded model version is SSD (Segmind Stable Diffusion 1B). Note that for an SSD model `_is_sdxl` will also be true. |
| `_is_sdxl_no_ssd`  | true if the loaded model version is SDXL and not an SSD model. |
| `_is_sdxl_no_pony` | true if the loaded model version is SDXL and not a Pony model (the "pony" variant must be defined in settings). Kept to maintain compatibility with previous versions. |
| `_is_vvvv`         | true if the loaded model matches the *vvvv* model variant definition (based on its filename). Note that the corresponding variable for the model kind will also be true. |
| `_is_pure_kkkk`    | true if the loaded model is of kind *kkkk* (f.e. sdxl) and not a variant. |
| `_is_variant_kkkk` | true if the loaded model version is any variant of model kind *kkkk* and not the pure version. Note that the corresponding variable for the model kind will also be true.|

### Example

(multiline to be easier to read)

```text
<ppp:if _is_sd1><lora:test_sd1> test sd1x
<ppp:elif _sd_pony><lora:test_pony> test pony
<ppp:elif _sd_pure_sdxl><lora:test_sdxl> test sdxl
<ppp:else>unknown model
<ppp:/if>
```

Only one of the options will end up in the prompt, depending on the loaded model.

## ExtraNetwork command

This command is a shortcut to add an extranetwork (usually a lora), and its triggers, with conditions. More legible and sometimes shorter than adding regular extranetworks inside if commands.

The full format is:

`<ppp:ext type name [parameters] [if condition]>[triggers]<ppp:/ext>`
`<ppp:ext type name [parameters] [if condition]>`

The `type` is the kind of extranetwork, like `lora` or `hypernet`.

The `name` is the extranetwork identifier. If it is not a regular identifier (i.e. starts with a number or contains spaces or symbols) it should be inside quotes.

The `parameters` is optional and its format depends on the extranetwork type. With loras or hypernets it is usually a single weight number, so if the type is one of those and there are no parameters it will default to `1`. If it is not a number it should go inside quotes.

The `condition` uses the same format as in the `if` command, and it is also optional.

The `triggers` are also optional, and can be any content. If there are no triggers the command ending can be omitted.

If the condition passes (or if there is no condition) the extranetwork tag will be built and added to the result along with any triggers.

### Examples

(multiline to be easier to read)

```text
<ppp:ext lora test_sd1 if _is_sd1>test sd1x<ppp:/ext>
<ppp:ext lora test_pony 0.5 if _is_pony>test pony<ppp:/ext>
<ppp:ext lora test_ilxl if _is_illustrious>
<ppp:ext lora 'test sdxl' '1:0.8' if _is_pure_sdxl>test sdxl<ppp:/ext>
```

Will turn into one of these (or none) depending on the model:

* `<lora:test_sd1:1>test sd1x`
* `<lora:test_pony:0.5>test pony`
* `<lora:test_illustrious:1>`
* `<lora:test sdxl:1:0.8>test sdxl`

### Extranetworks mappings

The extranetwork command supports specifying mappings of extranetworks, so a different lora can be used depending on the loaded model.

If the type of extranetwork is prefixed with a `$` the command will look for a mapping.

The mappings are configured in yaml files in any of the configured extranetwork mappings folders. The format is like this:

```yaml
extnettype:
  mappingname:
    - condition: "<a supported condition>"
      name: "<name of the extranetwork>"
      parameters: "<parameters of the extranetwork>"
      triggers: [<list of triggers>]
    ...
```

Used like this:

```text
<ppp:ext $lora mappingname>
<ppp:ext $lora mappingname>inline triggers<ppp:/ext>
```

Each mapping can have any number of elements in its list of mappings. There are no mandatory properties for a mapping. The properties mean the following:

* `condition`: the condition to check for this mapping to be used (usually it should be one of the `_is_*` variables). If the conditions of multiple mappings evaluate to True, one will be chosen randomly. If the condition is missing it is considered True, to be used in the last mapping to catch as an "else" condition, and will be used if no other mapping applies.
* `name`: name of the real extranetwork. If it is missing no extranetwork tag will be added.
* `parameters`: parameters for the real extranetwork. If it is missing it is assumed "1" for loras and hypernets. If both this parameter and the parameter in the ext command are numbers they are multiplied for the result. In other case the parameter of the ext command, if it exists, is used.
* `triggers`: list of trigger strings. If it is missing, only the inline triggers in the ext command will be added.
* `weight`: weight for this variant, in case multiple of them apply, to choose one. Default is 1.

See the file in the tests folder as an example.

## Sending content to the negative prompt

The new format for this command is like this:

| Construct                             | Meaning |
| ---------                             | ------- |
| `<ppp:stn position>content<ppp:/stn>` | send to negative prompt |
| `<ppp:stn iN>`                        | insertion point to be used in the negative prompt as destination for the pN position |

Where position is optional (defaults to the start) and can be:

* **s**: at the start of the negative prompt
* **e**: at the end of the negative prompt
* **pN**: at the position of the insertion point in the negative prompt with N being 0-9. If the insertion point is not found it inserts at the start.

### Example

You have a wildcard for hair colors (`__haircolors__`) with one being strawberry blonde, but you don't want strawberries. So in that option you add a command to add to the negative prompt, like so:

```text
blonde
strawberry blonde <ppp:stn>strawberry<ppp:/stn>
brunette
```

Then, if that option is chosen this extension will process it later and move that part to the negative prompt.

### Old format

The old format (`<!...!>`) is not supported anymore.

### Notes

Positional insertion commands have less priority that start/end commands, so even if they are at the start or end of the negative prompt, they will end up inside any start/end (and default position) commands.

The content of the negative commands is not processed and is copied as-is to the negative prompt. Other modifiers around the commands are processed in the following way.

### Attention modifiers (weights)

They will be translated to the negative prompt. For example:

* `(red<ppp:stn>square<ppp:/stn>:1.5)` will end up as `(square:1.5)` in the negative prompt
* `(red[<ppp:stn>square<ppp:/stn>]:1.5)` will end up as `(square:1.35)` in the negative prompt (weight=1.5*0.9) if the merge attention option is enabled or `([square]:1.5)` otherwise.
* However `(red<ppp:stn>[square]<ppp:/stn>:1.5)` will end up as `([square]:1.5)` in the negative prompt. The content of the negative tag is copied as is, and is not merged with the surrounding modifier because the insertions happen after the attention merging.

### Prompt editing constructs (alternation and scheduling)

Negative commands inside such constructs will copy the construct to the negative prompt, but separating its elements. For example:

* **Alternation**: `[red<ppp:stn>square<ppp:/stn>|blue<ppp:stn>circle<ppp:/stn>]` will end up as `[square|], [|circle]` in the negative prompt, instead of `[square|circle]`
* **Scheduling**: `[red<ppp:stn>square<ppp:/stn>:blue<ppp:stn>circle<ppp:/stn>:0.5]` will end up as `[square::0.5], [:circle:0.5]` instead of `[square:circle:0.5]`

This should still work as intended, and the only negative point i see is the unnecessary separators.
