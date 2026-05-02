# Cookbook

This cookbook shows some interesting uses of the features available.

## Wildcard definition

### Grouping

The common use of wildcards is creating multiple of them with simple lists of elements. But this extension supports more interesting ways to group the elements, reducing bloat and improving selection of the wanted elements.

In these examples we assume we want to select colors but we want warm colors to have double weight than cold colors, then have weights for each of them, and we sometimes want to choose only the warm ones, the cold ones, or any of them.

The usual way would be this:

```yaml
colors_warm:
    - 3::red
    - 2::orange
    - 1::yellow
colors_cold:
    - 2::blue
    - 1::green
```

And use `__colors_warm__` or `__colors_cold__`, or `{2::__colors_warm__|1::__colors_cold__}` to get all of them.

The `1` weights are not necessary, it just makes the intent clearer.

#### Filters

You can add labels to the elements of a wildcard, allowing you to reduce the availability to only a subset of them. This avoids the need to create multiple wildcards of similar elements.

```yaml
colors:
    - "'warm'6::red"
    - "'warm'4::orange"
    - "'warm'2::yellow"
    - "'cold'2::blue"
    - "'cold'1::green"
```

And use `__colors'warm'__` or `__colors'cold'__`, or just `__colors__` to get all of them.

Labels can be more complex than this. See the syntax document.

#### Anonymous wildcards

You can also group the elements by using anonymous wildcards, which can also be labeled.

```yaml
colors:
    - "'warm'2":  # this needs double quotes to include the single quotes as part of the options
        - 3::red
        - 2::orange
        - 1::yellow
    - "'cold'1":
        - 2::blue
        - 1::green
```

And use `__colors'warm'__` or `__colors'cold'__`, or just `__colors__` to get all of them.

This produces almost the same effect as before but is easier to read. The only difference is with the weights when you don't filter, because now it first chooses between the warm and the cold options and then the colors inside the chosen one. This allows you to add simpler weights to the two groups and their elements instead of having to calculate the combined weights.

With simple labels this is probably the best method.

#### Wildcard inclusion

Another option, but not as clean, is to include wildcards inside other wildcards.

```yaml
colors_warm:
    - 3::red
    - 2::orange
    - 1::yellow
colors_cold:
    - 2::blue
    - 1::green
colors:
    - "%'warm'2::include colors_warm"
    - "%'cold'1::include colors_cold"
```

Then use `__colors_warm__` or `__colors_cold__`, or `__colors'warm'__` or `__colors'cold'__` or `__colors__` to get all of them.

## Prompt building

You can create a complex set of wildcards that build a full prompt, by using the wildcards along with variables with default values. The variables allow you to choose what parts of the prompt you want to change for specific content, or just leave the defaults. Then, inside the UI, you can use styles (with an appropiate styles node if using ComfyUI) to choose which variables to set. This makes it easy to quickly select what do you want to prompt for.

Wildcards:

```yaml
style:
    realistic: photograph
    oil: oil painting
    sketch: pencil sketch

subject:
    - "'human'::{man|woman}"
    - "'orc,fantasy'::orc"
    - "'goblin,fantasy'::goblin"

clothes:
    - "'regular'::t-shirt, pants, shoes"
    - "'regular'::swimsuit"
    - "'regular'::uniform"
    - "'regular'::pajamas"
    - "'armor'::metal armor"
    - "'armor'::leather armor"

action:
    - "'passive'::standing"
    - "'passive'::sitting"
    - "'passive'::lying down"
    - "'passive'::crouching"
    - "'active'::running"
    - "'active'::dancing"
    - "'active'::driving"

background:
    home:
        - in the kitchen
        - in the bathroom
        - in the living room
    nature:
        - in a forest
        - in a swamp
        - in a desert
        - in a grotto
        - in the beach
    building:
        - in a cathedral
        - in an office
        - in a store
        - in a castle
        - in a dungeon
    any: "{__background/home__|__background/nature__|__background/building__}"

character:
  - "${style:()}, ${subject:__subject'human'__}, ${clothes:__clothes'regular'__}, ${action:__action'passive'__}, ${background:__background/any__}"
```

Styles file:

```csv
name,prompt,negative_prompt
"Nothing","",""
"Style: realistic","${style=__style/realistic__}",""
"Style: oil","${style=__style/oil__}",""
"Style: sketch","${style=__style/sketch__}",""
"Subject: human","${subject=__subject'human'__}",""
"Subject: orc","${subject=__subject'orc'__}",""
"Subject: goblin","${subject=__subject'goblin'__}",""
"Subject: fantasy","${subject=__subject'fantasy'__}",""
"Subject: any","${subject=__subject__}",""
"Clothes: regular","${clothes=__clothes'regular'__}",""
"Clothes: armor","${clothes=__clothes'armor'__}",""
"Clothes: any","${clothes=__clothes__}",""
"Action: passive","${action=__action'passive'__}",""
"Action: active","${action=__action'active'__}",""
"Action: any","${action=__action__}",""
"Background: home","${background=__background/home__}",""
"Background: nature","${background=__background/nature__}",""
"Background: building","${background=__background/building__}",""
"Background: any","${background=__background/any__}",""
"Character","__character__",""
```

You first select the styles that set the variables that you are interested in changing from the default, and you end with the main wildcard that uses them to build the prompt. Note that the order of the variables don't usually matter because they are only evaluated when echoed to the prompt. This allows you to use variables inside wildcards that are inside other variables, and only at the end they will be evaluated.

Sample style selections:

Sample 1:

- "Style: oil"
- "Subject human"
- "Clothes: regular"
- "Background: home"
- "Character"

This would create this prompt:

`${style=__style/oil__}, ${subject=__subject'human'__}, ${clothes=__clothes'regular'__}, ${background=__background/home__}, __character__`

Sample 2:

- "Subject: fantasy"
- "Clothes: armor"
- "Action: active"
- "Background: nature"
- "Character"

This would create this prompt:

`${subject=__subject'fantasy'__}, ${clothes=__clothes'armor'__}, ${action=__action'active'__}, ${background=__background/nature__}, __character__`

## Using variables for detailer prompts

This only applies to ComfyUI, because the variables cannot be used in the ADetailer prompts of the A1111 UIs.

You can put parts of the prompt to be set into variables, and then extract this variables from the output and use them in the prompts of the detailer nodes.

For example, imagine you have this prompt:

`Cyberpunk woman with ${head:long red hair mohawk, green eyes, and neon makeup} riding a futuristic motorcycle`

That will create a variable `head` with the head description and insert it in that position in the prompt. That variable can then be extracted with the "**ACB PPP Select Variable**" node and used as input for the detailer for the head, thus avoiding prompt clutter that does not apply.

## Conditional content based on model

The `_is_*` system variables let you write a single prompt that adapts automatically to the loaded model. This is especially useful for LoRAs that exist in different versions for different model families.

```text
beautiful woman in a garden
<ppp:if _is_sd1><lora:woman_detail_sd1:0.8> detailed face<ppp:elif _is_sdxl><lora:woman_detail_xl:0.9> detailed face<ppp:elif _is_flux><lora:woman_detail_flux:1.0> detailed face<ppp:/if>
```

Only one branch ends up in the final prompt. You can also nest `if` commands inside wildcards to gate certain choices:

```yaml
poses:
    - "'standing'::standing upright"
    - "'sitting'::sitting on a bench"
    - "'dynamic,sdxl'if _is_sdxl::dynamic action pose"
    - "'dynamic,flux'if _is_flux::powerful dynamic pose, motion blur"
```

The last two entries are only available when their respective model is loaded.

## ExtraNetworks mappings

When you have the same LoRA in multiple versions (one per model family), you can create a mapping so the correct one is picked automatically without rewriting your prompt for each model.

**Mapping file** (`enmappings/my_loras.yaml`):

```yaml
lora:
  my_character:
    - condition: "_is_sd1"
      name: "my_character_sd1"
      parameters: "0.8"
      triggers: ["my_char_trigger"]
    - condition: "_is_sdxl"
      name: "my_character_xl"
      parameters: "0.9"
      triggers: ["my_char_trigger", "detailed"]
    - condition: "_is_flux"
      name: "my_character_flux"
      parameters: "1.0"
      triggers: ["my_char_trigger"]
```

**Prompt usage:**

```text
a portrait of <ppp:ext $lora my_character>extra trigger<ppp:/ext>
```

The extension picks the mapping whose condition matches the loaded model, builds the correct `<lora:...:...>` tag, prepends the triggers from the mapping, and appends the inline triggers. If no condition matches (e.g. an unsupported model) nothing is added.

You can also specify a weight multiplier directly in the command - if both the command weight and the mapping `parameters` are numbers, they are multiplied:

```text
<ppp:ext $lora my_character 0.75/>
```

## Send-to-negative with attention modifiers

When a send-to-negative command sits inside an attention modifier, the weight is carried over to the negative prompt. There is one important distinction:

```text
(red apple<ppp:stn>round shape<ppp:/stn>:1.4)
```

Result in the negative: `(round shape:1.4)` - the surrounding weight is applied.

```text
(red apple<ppp:stn>[round shape]<ppp:/stn>:1.4)
```

Result in the negative: `([round shape]:1.4)` - the weight is **not** merged into the inner brackets, because the content of the negative tag is copied as-is and the merge happens before the tag is processed.

```text
(red [apple<ppp:stn>round shape<ppp:/stn>]:1.4)
```

Result in the negative: `(round shape:1.26)` - if merge attention is enabled, `1.4 × 0.9 = 1.26` is applied.

Keep this in mind when writing choices in wildcards that combine attention brackets with send-to-negative.

## Array variables

Arrays let you collect several values and then use them together, which is useful when you want to pick a random set of attributes and later echo them as a formatted list.

**Example - picking random accessories:**

```text
${accessories[]=*__accessories__}
a woman wearing ${accessories[&', ']}
```

The wildcard `__accessories__` is expanded into an array, then echoed as a comma-separated string.

**Example - building a list of a fixed size from separate wildcards:**

```text
${colors[]=*__colors__}
${colors[]+=*__materials__}
abstract composition of ${colors[&' and ']}
```

**Initializing from a literal list:**

```text
${seasons[]=*('spring', 'summer', 'autumn', 'winter')}
seasonal scene: ${seasons[&', ']}
```

## Conditional filtering inside wildcards

You can attach an `if` condition directly to a choice inside a wildcard, making the choice invisible unless the condition is true. This lets a single wildcard file serve all model families without duplication.

```yaml
lora_styles:
    - "'painterly'::painterly style, oil paint"
    - "'anime'if _is_sd1 or _is_sdxl::anime style, flat shading"
    - "'photorealistic'if _is_sdxl or _is_flux::photorealistic, hyper detailed"
    - "'concept'if _is_flux::concept art, cinematic lighting"
```

When loaded with SD 1, only `painterly` and `anime` are available. When loaded with Flux, only `painterly`, `photorealistic`, and `concept` are.

You can combine conditions with `and`, `or`, and `not`, and reference any user or system variable:

```yaml
effects:
    - "bokeh, shallow depth of field"
    - "long exposure, motion blur"
    - "'hdr'if _is_sdxl or _is_flux::HDR, high dynamic range"
    - "'film'if quality ne 'draft'::film grain, subtle noise"
```

## `setwcdeffilter` for dynamic routing

`setwcdeffilter` sets a default filter on a wildcard before it is referenced anywhere in the prompt. This avoids having to repeat a filter at every call site when you want to pre-select a subset of choices.

A typical use case is a style variable that narrows what a downstream wildcard will pick:

```text
<ppp:setwcdeffilter 'clothing' 'armor'/>
A warrior ${subject} wearing __clothing__
```

Whatever label filter you pass becomes the default for that wildcard for the rest of the current generation.

You can use globbing to apply the filter to a whole family of wildcards:

```text
<ppp:setwcdeffilter 'items/*' 'rare'/>
```

This pre-filters every wildcard under `items/` to only `rare`-labelled choices. To remove a previously set default filter:

```text
<ppp:setwcdeffilter 'items/*'/>
```

A practical workflow combining this with variables and styles:

```csv
name,prompt,negative_prompt
"Gear: armor","<ppp:setwcdeffilter 'clothing' 'armor'/>",""
"Gear: casual","<ppp:setwcdeffilter 'clothing' 'casual'/>",""
"Character","__character__",""
```

Select a "Gear" style first and then "Character" - the wildcard inside `character` will automatically use the pre-filtered `clothing` choices.

## Globbing wildcards

Instead of referencing a single wildcard file, you can use glob patterns to merge choices from multiple files into one pool. This is handy when you split a large collection into smaller themed files.

File layout:

```text
wildcards/
  characters/
    humans.yaml
    orcs.yaml
    elves.yaml
```

Each file is a regular YAML wildcard. Reference them all at once:

```text
__characters/*__
```

This merges all choices from `humans.yaml`, `orcs.yaml`, and `elves.yaml` into a single pool and picks one.

Note that the globbing works on the wildcard key, not the file structure. So if those files contain multiple wildcards, all of them will be merged.

You can apply parameters to the glob call just like a regular wildcard:

```text
__2$$ / $$characters/*__
```

Selects 2 choices from the merged pool, separated by " / ".

You can also apply a filter to narrow from within the merged pool:

```text
__characters/*'fantasy'__
```

Only choices labelled `fantasy` across all matched files are eligible.

Note: if no parameters are specified in the glob call, the parameters from the first matching file that defines them (sorted by key) are used. To avoid that, specify parameters explicitly in the call.

## Prefix/suffix on wildcard parameters

Using the object format for wildcard parameters you can add a prefix and/or suffix that wrap every result. This is cleaner than repeating the wrapper in each choice.

Without prefix/suffix, every choice needs to repeat the attention modifier:

```yaml
qualities:
    - "(ultra detailed:1.3)"
    - "(highly detailed:1.3)"
    - "(intricate details:1.3)"
```

With object-format parameters and a prefix/suffix:

```yaml
qualities:
    - { prefix: "(", suffix: ":1.3)" }  # parameters line
    - "ultra detailed"
    - "highly detailed"
    - "intricate details"
```

The prefix and suffix are added around the joined result (including the separator when multiple choices are selected). They can themselves contain constructs.

## `ifundefined` / `?=` for safe defaults

When building multi-style workflows you often want a variable to have a sensible default that can be overridden by an earlier style, but only if it hasn't already been set. The `ifundefined` modifier (`?=`) is designed for this.

```text
${quality?=__qualities__}, ${style?=photograph}, ${subject?=__subject__}
```

If a "Quality: ultra" style already ran `${quality=ultra detailed, 8k}` earlier in the pipeline, the `?=` here does nothing. If no quality style was chosen, it picks a random value from `__qualities__` as the fallback.

This is more robust than relying on the order of styles. But if you need a specific default for different instances use instead the default value when echoing the variable.

**Styles file example:**

```csv
name,prompt,negative_prompt
"Quality: draft","${quality=draft quality}",""
"Quality: high","${quality=ultra detailed, 8k}",""
"Style: photo","${style=photograph}",""
"Style: painting","${style=oil painting}",""
"Character","${quality?=__qualities__}, ${style?=photograph}, __subject__",""
```

If the user selects "Quality: high" and "Character", quality is `ultra detailed, 8k`. If they select only "Character", quality falls back to a random value from `__qualities__`.

You can also use `evaluate ifundefined` (`?=!`) to resolve the wildcard immediately rather than lazily:

```text
${quality?=!__qualities__}
```

## Debugging tips

When something isn't generating as expected, the debug setting is your first tool. Enable it in the extension settings; it will log all system variables at generation time, which tells you exactly what values are available for your conditions.

**Finding the right system variable for an unsupported model:**

If you load a model that isn't matched by any `_is_*` variable, check `_modelclass` in the debug log. Use it directly in a condition while you wait for official support:

```text
<ppp:if _modelclass eq 'StableDiffusionXLPipeline'>content for new model<ppp:/if>
```

**Inspecting variable values mid-prompt:**

Insert a temporary `echo` to see what a variable resolves to:

```text
[DEBUG style=${style}] ${style:photograph}, detailed portrait
```

Remove the bracketed part once you're satisfied.

**Checking which choices are available after filtering:**

If a wildcard seems to produce unexpected results, temporarily use a fixed positional filter to verify specific choices:

```text
__mywildcard'0'__   # always picks the first choice
__mywildcard'1'__   # always picks the second choice
```

This confirms the order and content of choices before relying on label filters.

**Common pitfalls:**

- A `%` choice in a YAML array must be quoted, otherwise YAML treats `%` as invalid syntax.
- Variables set with `${var=value}` are lazy - they are not evaluated until echoed. Use `${var=!__wildcard__}` (with `!`) for immediate evaluation if the value should only be resolved once (as in, you want the same value to be echoed later multiple times).
- Wildcards cannot be used inside extranetwork tags (because some LoRA names contain double underscores). Put the entire `<lora:...>` tag inside a wildcard choice instead, or use the `ext` command.
