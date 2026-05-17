# ACB Prompt Post Processor node

Main PPP node that processes prompts.

## Inputs

* **model**: Connect here the MODEL or a string with the model class name used by *ComfyUI*. Needed for the model kind system variables.
* **modelname**: Filename of the model (with relative path). Needed for the detection of model variants.
* **seed**: Set or connect here the seed used. By default it is -1 (random). The actual value used can be extracted from the output variables (`_input_seed`).
* **pos_prompt**: Connect here the prompt text, or fill it as a widget.
* **neg_prompt**: Connect here the negative prompt text, or fill it as a widget.
* **debug_level**: What to write to the console.
* **on_warnings**: Warn on the console or stop the generation.
* **strict_mode**: Sets the strict mode in comparison operations.
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

> [!NOTE]
> The node uses 32-bit seeds, to be compatible with all the UIs. This means that 64-bit input values will be cut at 32-bits. If you connect an external seed that is also connected directly to the ksampler, the values may differ. This doesn't really matter in practice, but if you want the same value use the output `_input_seed` variable to send to the ksampler.

The options nodes are optional. If you don't need to change any of the default values then you don't need to use them.

The model and modelname are also optional, but if you don't set them you will not be capable of choosing content based on the model type or variant. Native model loader nodes do not output the filename, but there are custom nodes that do (like those from [ComfyUI Image Saver](https://github.com/alexopus/ComfyUI-Image-Saver)).

Setting only the modelname will try to detect its class from the file contents. If you don't want to set the path twice (and you don't use a loader node that outputs the name), you can set it here and then extract it from the output variables (`_modelfullname`) to send to the loader node.

You can instead set them from the prompt and load the model afterwards.

## Outputs

* **pos_prompt**: Resulting positive prompt.
* **neg_prompt**: Resulting negative prompt.
* **variables**: Resulting output variables.

The outputs are lists, and in combinatorial mode there will be multiple elements that *ComfyUI* will process sequentially.

## Notes

You can use the "**ACB PPP Select Variable**" node to choose one and output its value. You can use this to send only part of the prompt to, for example, a detailer node. For example:

With this prompt: `__quality__, 1girl, ${head:!__eyes__, __hair__, __expression__}, __body__, __clothes__, __background__, __style__` then you extract the `head` variable and use `${head}` as prompt for the head/face detailer.
