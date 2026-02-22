# ACB PPP Wildcard Options node

* **folders**: You can enter multiple folders separated by commas. You can leave it empty (the default) and add a `ppp_wildcards` or `wildcards` entry in the **extra_model_paths.yaml** file (recommended).
* **definitions**: Wildcards definitions (in yaml or json format). Direct input added to the ones found in the wildcards folders. Allows wildcards to be included in the workflow.
* **if_wildcards**: Select what do you want to do with any found wildcards/choices (when process wildcards is off or after the processing).
  * **Ignore**: do not try to detect wildcards.
  * **Remove**: detect wildcards and remove them.
  * **Add visible warning**: detect wildcards and add a warning text to the prompt, that hopefully produces a noticeable generation.
  * **Stop the generation**: detect wildcards and stop the generation.
* **choice_separator**: What do you want to use by default to separate multiple choices when the options allow it (by default it's ', ").
* **keep_choices_order**: If checked, a multiple choice construct will return them in the order they are in the construct.
