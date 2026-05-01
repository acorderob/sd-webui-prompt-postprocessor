# Prompt PostProcessor configuration

## Configuration file

The extension supports a configuration file `ppp_config.yaml` with some settings that don't usually change.

By default this configuration is read from the file `ppp_config.yaml.defaults` in the extension folder. That file must not be modified. If you want to personalize any settings you should first copy it as `ppp_config.yaml` in the same folder, or in the ComfyUI user folder (preferred, but only possible in ComfyUI). The options in this new file will take precedence over those in the defaults file.

This file contains some options for how the host applications (WebUIs) should act in certain operations, and also define the supported models, including how to detect them and the model variants definitions. Host names are fixed values (those supported by the extension). The defaults file contains comments to explain the available options.

The model variants now support regular expressions instead of a list of strings to detect the variant. If you used a non default value in previous versions you should create a configuration file and add them with the new format. As before, the default file defines variants for *Pony* and *Illustrious* models.

## ComfyUI

### ACB Prompt Post Processor node

The main node that processes the prompt.

Inputs:

* **model**: Connect here the MODEL or a string with the model class name used by *ComfyUI*. Needed for the model kind system variables.
* **modelname**: Name of the model. Needed for the detection of model variants.
* **seed**: Connect here the seed used. By default it is -1 (random).
* **pos_prompt**: Connect here the prompt text, or fill it as a widget.
* **neg_prompt**: Connect here the negative prompt text, or fill it as a widget.
* **debug_level**: What to write to the console.
* **on_warnings**: Warn on the console or stop the generation.
* **strict_mode**: Sets the strict mode in comparison operations.
* **process_wildcards**: Activates the wildcard processing.
* **do_cleanup**: Activates the cleanup processing.
* **cleanup_variables**: Do a cleanup of the output variables (depends on do_cleanup).
* **do_combinatorial**: Activates combinatorial mode, where the output are all the combinations of choices/wildcards of the prompt.
* **combinatorial_limit**: Limit for the number of generated combinations.
* **wc_options**: Connection to a Wildcards options node.
* **stn_options**: Connection to a Send-To-Negative options node.
* **cup_options**: Connection to a Cleanup options node.
* **en_options**: Connection to a ExtraNetworkMapping options node.

The options nodes are optional. If you don't need to change any of the default values then you don't need to use them.

Outputs:

* **pos_prompt**: the resulting positive prompt
* **neg_prompt**: the resulting negative prompt
* **variables**: the dictionary of variables set or echoed.

The outputs are lists, and in combinatorial mode there will be multiple elements that ComfyUI will process sequentially.

### ACB PPP Select Variable node

Lets you extract the variables used from the output (or just one of them). You can use this to send only part of the prompt to, for example, a detailer node. For example:

With this prompt: `__quality__, 1girl, ${head:__eyes__, __hair__, __expression__}, __body__, __clothes__, __background__, __style__` then you extract the `head` variable and use it as prompt for the head/face detailer.

Inputs:

* **variables**: the variables dictionary from the main node output.
* **name**: optional name of a variable.

Output:

* **value**: the resulting content, either all the variables (one per line, in "name: value" format) or just the content of the chosen one.

### ACB PPP Wildcards Concat node

This node lets you select up to 10 wildcards that will be concatenated with a chosen separator. You can't specify wildcard folders in the node, so use the other available options to set them.

Inputs:

* **previous_prompt**: An optional text that will be prepended to the wildcards. Lets you chain multiple nodes or other string nodes.
* **filter**: a string to filter the identifiers of the wildcards. It matches the start of the identifiers.
* **separator**: a separator string.
* **wildcard_<n>**: the wildcards to concatenate.

Output:

* **prompt**: concatenated result.

### ACB PPP Wildcard Options node

Options for wildcard processing, in case you want to change them from the defaults.

* **folders**: You can enter multiple folders separated by commas. You can leave it empty (the default) and add a `ppp_wildcards` or `wildcards` entry in the **extra_model_paths.yaml** file (recommended).
* **definitions**: Wildcards definitions (in yaml or json format). Direct input added to the ones found in the wildcards folders. Allows wildcards to be included in the workflow.
* **if_wildcards**: Select what do you want to do with any found wildcards/choices (when process wildcards is off or after the processing).
  * **Ignore**: do not try to detect wildcards.
  * **Remove**: detect wildcards and remove them.
  * **Add visible warning**: detect wildcards and add a warning text to the prompt, that hopefully produces a noticeable generation.
  * **Stop the generation**: detect wildcards and stop the generation.
* **choice_separator**: What do you want to use by default to separate multiple choices when the options allow it (by default it's ', ").
* **keep_choices_order**: If checked, a multiple choice construct will return them in the order they are in the construct.

### ACB PPP Send-To-Negative Options node

Options for sent to negative commands, in case you want to change them from the defaults.

* **separator**: You can specify the separator used when adding to the negative prompt (by default it's ", ").
* **ignore_repeats**: It ignores repeated content to avoid repetitions in the negative prompt.

### ACB PPP Cleanup Options node

Options for cleanup processing, in case you want to change them from the defaults.

* **extra_spaces**: Removes other unnecessary spaces.
* **empty_constructs**: Removes attention/scheduling/alternation constructs when they are invalid.
* **extra_separators**: Removes unnecessary separators. This applies to the configured separator and regular commas.
* **extra_separators_additional**: Removes unnecessary separators at start or end of lines. This applies to the configured separator and regular commas.
* **extra_separators_include_eol**: In the previous two options it also removes EOLs attached to the separators.
* **around_breaks**: Removes consecutive BREAKs and unnecessary commas and space around them.
* **breaks_with_eol**: Add a newline before BREAKs.
* **around_ands**: Removes consecutive ANDs and unnecessary commas and space around them.
* **ands_with_eol**: Add a newline before ANDs.
* **around_extranetwork_tags**: Removes spaces around extra network tags.
* **merge_attention**: It merges attention modifiers when possible (merges into one, multiplying their values). Only merges individually nested modifiers.
* **remove_extranetwork_tags**: Removes all extra network tags.

Please note that *ComfyUI* does not natively support the `BREAK` and `AND` constructs, but the related settings are kept in that UI in case you use a node that supports them and the extension is configured to allow them (see the configuration file below).

### ACB PPP ExtraNetwork Mapping Options node

Options for extranetworks mapping, in case you want to change them from the defaults.

* **folders**: You can enter multiple folders separated by commas. You can leave it empty (the default) and add a `ppp_extranetworkmappings` entry in the **extra_model_paths.yaml** file (recommended).
* **definitions**: Extranetwork Mappings definitions (in yaml format). Direct input added to the ones found in the extranetwork mappings folders. Allows the mappings to be included in the workflow.

## A1111 (and compatible UIs)

### Panel options

* **Force equal seeds**: Changes the image seeds and variation seeds to be equal to the first of the batch. This allows using the same values for all the images in a batch.
* **Unlink seed**: Uses the specified seed for the prompt generation instead of the one from the image. This seed is only used for wildcards and choices.
* **Prompt seed**: The seed to use for the prompt generation. If -1 a random one will be used.
* **Incremental seed**: When using a batch you can use this to set the rest of the prompt seeds with consecutive values.
* **Combinatorial mode**: Generate all possible prompt combinations (from choices and wildcards) and cycle through them to fill the batch.
* **Combinations limit**: Maximum number of combinations to generate (0 = no limit). When generating a batch the limit is automatically raised to at least the batch size.

### General settings

* **Debug level**: What to write to the console. Note: in *SD.Next* debug messages only show if you launch it with the `--debug` argument.
* **What to do on invalid content warnings**: Warn on the console or stop the generation. This also affects the use of unknown variables, and integer comparisons with undefined or non-numeric variables: in *warn* mode the comparison evaluates to false, in *stop* mode the generation is stopped with an error.
* **Use strict operators**: Sets strict operations in comparisons.
* **Apply in img2img**: Check if you want to do the processing in img2img processes.
* **Add original prompts to metadata**: Adds original prompts to the metadata if they have changed.
* **Extranetwork Mappings folders**: You can enter multiple folders separated by commas.

### Wildcard settings

* **Process wildcards**: You can choose to process wildcards and choices with this extension or use a different one.
* **Wildcards folders**: You can enter multiple folders separated by commas.
* **What to do with remaining wildcards?**: Select what do you want to do with any found wildcards/choices (when process wildcards is off or after the processing).
  * **Ignore**: Do not try to detect wildcards.
  * **Remove**: Detect wildcards and remove them.
  * **Add visible warning**: Detect wildcards and add a warning text to the prompt, that hopefully produces a noticeable generation.
  * **Stop the generation**: Detect wildcards and stop the generation.
* **Default separator used when adding multiple choices**: What do you want to use by default to separate multiple choices when the options allow it (by default it's ", ").
* **Keep the order of selected choices**: If checked, a multiple choice construct will return them in the order they are in the construct.

### Send to negative prompt settings

* **Separator used when adding to the negative prompt**: You can specify the separator used when adding to the negative prompt (by default it's ", ").
* **Ignore repeated content**: It ignores repeated content to avoid repetitions in the negative prompt.

### Clean up settings

* **Remove empty constructs**: Removes attention/scheduling/alternation constructs when they are invalid.
* **Remove extra separators**: Removes unnecessary separators. This applies to the configured separator and regular commas.
* **Remove additional extra separators**: Removes unnecessary separators at start or end of lines. This applies to the configured separator and regular commas.
* **The extra separators options also remove EOLs**: In the previous two options it also removes EOLs attached to the separators.
* **Clean up around BREAKs**: Removes consecutive BREAKs and unnecessary commas and space around them.
* **Use EOL instead of Space before BREAKs**: Add a newline before BREAKs.
* **Clean up around ANDs**: Removes consecutive ANDs and unnecessary commas and space around them.
* **Use EOL instead of Space before ANDs**: Add a newline before ANDs.
* **Clean up around extra network tags**: Removes spaces around extra network tags.
* **Merge attention modifiers (weights) when possible**: It merges attention modifiers when possible (merges into one, multiplying their values). Only merges individually nested modifiers.
* **Remove extra spaces**: Removes other unnecessary spaces.
* **Remove extra network tags**: Removes all extra network tags.
