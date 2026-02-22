# ACB PPP Cleanup Options node

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
