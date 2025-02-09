# Prompt PostProcessor for Stable Diffusion WebUI and ComfyUI

The Prompt PostProcessor (PPP), formerly known as "sd-webui-sendtonegative", is an extension designed to process the prompt, possibly after other extensions have modified it. This extension is compatible with:

* [AUTOMATIC1111 Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
* [Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge)
* [reForge](https://github.com/Panchovix/stable-diffusion-webui-reForge)
* [SD.Next](https://github.com/vladmandic/automatic)
* ...and probably other forks
* [ComfyUI](https://github.com/comfyanonymous/ComfyUI)

Currently this extension has these functions:

* Sending parts of the prompt to the negative prompt. This allows for useful tricks when using wildcards since you can add negative content from choices made in the positive prompt.
* Set and modify local variables.
* Filter content based on the loaded SD model or a variable.
* Process wildcards. Compatible with Dynamic Prompts formats. Can also detect invalid wildcards and act as you choose.
* Clean up the prompt and negative prompt.

Note: when used in an *A1111* compatible webui, the extension must be loaded after any other extension that modifies the prompt (like another wildcards extension). Usually extensions load by their folder name in alphanumeric order, so if the extensions are not loading in the correct order just rename this extension's folder so the ordering works out. When in doubt, just rename this extension's folder with a "z" in front (for example) so that it is the last one to load, or manually set such folder name when installing it.

If the extension runs before others, like Dynamic Prompts, and the "Process wildcards" is enabled, the wildcards will be processed by PPP and those extensions will not get them. If you disable processing the wildcards, and intend another extension to process them, you should keep the "What to do with remaining wildcards?" option as "ignore".

Notes:

1. Other than its own commands, it only recognizes regular *A1111* prompt formats. So:

    * **Attention**: `[prompt] (prompt) (prompt:weight)`
    * **Alternation**: `[prompt1|prompt2|...]`
    * **Scheduling**: `[prompt1:prompt2:step]`
    * **Extra networks**: `<kind:model...>`
    * **BREAK**: `prompt1 BREAK prompt2`
    * **Composable Diffusion**: `prompt1:weight1 AND prompt2:weight2`

    In *SD.Next* that means only the *A1111* or *Full* parsers. It will warn you if you use the *Compel* parser.

    Does not recognize tokenizer separators like `TE2:` and `TE3:`, so sending to negative prompt from those sections of the prompt will not add them in the corresponding section of the negative prompt.

    *ComfyUI* only supports natively the attention using parenthesis, so the ones with the braces will be converted. The other constructs are not natively supported but some custom nodes implement them.
2. It recognizes wildcards in the `__wildcard__` and {choice|choice} formats (and almost everything that [Dynamic Prompts](https://github.com/adieyal/sd-dynamic-prompts) supports).
3. It does not create *AND/BREAK* constructs when moving content to the negative prompt.

## Installation

On *A1111* compatible webuis:

1. Go to Extensions > Install from URL
2. Paste <https://github.com/acorderob/sd-webui-prompt-postprocessor> in the URL for extension's git repository text field
3. Click the Install button
4. Restart the webui

On *SD.Next* I recommend you disable the native wildcard processing.

On *ComfyUI*:

1. Go to Manager > Custom Nodes Manager
2. Search for "Prompt PostProcessor" and install or click Install via Git URL and enter <https://github.com/acorderob/sd-webui-prompt-postprocessor>
3. Restart

## Usage

See the [syntax documentation](docs/SYNTAX.md).

## Configuration

See the [configuration documentation](docs/CONFIG.md).

## License

MIT

## Contact

If you have any questions or concerns, please leave an issue, or start a thread in the discussions.
