# Prompt PostProcessor configuration

## ComfyUI specific (ACB Prompt Post Processor node)

### Inputs

* **model**: Connect here the MODEL or a string with the model class name used by *ComfyUI*. Needed for the model kind system variables.
* **modelname**: Name of the model. Needed for the model name system variables and detection of pony (this also requieres for the model to be SDXL).
* **seed**: Connect here the seed used. By default it is -1 (random).
* **pos_prompt**: Connect here the prompt text, or fill it as a widget.
* **neg_prompt**: Connect here the negative prompt text, or fill it as a widget.
* **wc_wildcards_input**: Wildcards definitions (in yaml or json format). Direct input added to the ones found in the wildcards folders. Allows wildcards to be included in the workflow.

Other common settings (see [below](#common-settings)) also appear as inputs or widgets.

### Outputs

The outputs are the final positive and negative prompt and a variables dictionary.

You can use the "**ACB PPP Select Variable**" node to choose one and output its value. You can use this to send only part of the prompt to, for example, a detailer node. For example:

With this prompt: `__quality__, 1girl, ${head:__eyes__, __hair__, __expression__}, __body__, __clothes__, __background__, __style__` then you extract the `head` variable and send that as prompt for the head/face detailer.

## A1111 (and compatible UIs) panel options

* **Force equal seeds**: Changes the image seeds and variation seeds to be equal to the first of the batch. This allows using the same values for all the images in a batch.
* **Unlink seed**: Uses the specified seed for the prompt generation instead of the one from the image. This seed is only used for wildcards and choices.
* **Prompt seed**: The seed to use for the prompt generation. If -1 a random one will be used.
* **Incremental seed**: When using a batch you can use this to set the rest of the prompt seeds with consecutive values.

## Common settings

### General settings

* **Debug level**: what to write to the console. Note: in *SD.Next* debug messages only show if you launch it with the `--debug` argument.
* **Model variant definitions**: definitions for model variants to be recognized based on strings found in the full filename.

    The format for each line is (with *kind* being one of the base model identifiers or not defined):

    ```name(kind)=comma separated list of substrings (case insensitive)```

    The default value defines strings for *Pony* and *Illustrious* models.
* **Apply in img2img**: check if you want to do the processing in img2img processes (*does not apply to the ComfyUI node*).
* **Add original prompts to metadata**: adds original prompts to the metadata if they have changed (*does not apply to the ComfyUI node*).

### Wildcard settings

* **Process wildcards**: you can choose to process them with this extension or use a different one.
* **Wildcards folders**: you can enter multiple folders separated by commas. In *ComfyUI* you can leave it empty and add a `wildcards` entry in the **extra_model_paths.yaml** file.
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

Please note that *ComfyUI* does not natively support the `BREAK` and `AND` constructs, but the related settings are kept in that UI.

### Content removal settings

* **Remove extra network tags**: removes all extra network tags.
