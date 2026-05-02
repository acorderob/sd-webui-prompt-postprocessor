# ACB Prompt Post Processor node

## Inputs

* **model**: Connect here the MODEL or a string with the model class name used by *ComfyUI*. Needed for the model kind system variables.
* **modelname**: Name of the model. Needed for the detection of model variants.
* **seed**: Connect here the seed used. By default it is -1 (random).
* **pos_prompt**: Connect here the prompt text, or fill it as a widget.
* **neg_prompt**: Connect here the negative prompt text, or fill it as a widget.
* **debug_level**: What to write to the console.
* **on_warnings**: Warn on the console or stop the generation.
* **process_wildcards**: Activates the wildcard processing.
* **do_cleanup**: Activates the cleanup processing.
* **cleanup_variables**: Do a cleanup of the output variables (depends on do_cleanup).
* **do_combinatorial**: Activates combinatorial mode, where the output are all the combinations of choices/wildcards of the prompt.
* **combinatorial_shuffle**: It shuffles the combinatorial results.
* **combinatorial_limit**: Limit for the number of generated combinations.
* **wc_options**: Connection to a Wildcards options node.
* **stn_options**: Connection to a Send-To-Negative options node.
* **cup_options**: Connection to a Cleanup options node.
* **en_options**: Connection to a ExtraNetworkMapping options node.

The options nodes are optional. If you don't need to change any of the default values then you don't need to use them.

## Outputs

The outputs are the final positive and negative prompt and a variables dictionary.

You can use the "**ACB PPP Select Variable**" node to choose one and output its value. You can use this to send only part of the prompt to, for example, a detailer node. For example:

With this prompt: `__quality__, 1girl, ${head:!__eyes__, __hair__, __expression__}, __body__, __clothes__, __background__, __style__` then you extract the `head` variable and use `${head}` as prompt for the head/face detailer.
