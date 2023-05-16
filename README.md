# Send to Negative for Stable Diffusion WebUI

Extension for the [AUTOMATIC1111 Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) or compatible UIs.

## Purpose

This extension allows the tagging of parts of the prompt and moves them to the
negative prompt. This allows useful tricks when using a wildcard extension
since you can add negative content from choices made in the positive prompt.

Note: The extension must be loaded after the installed wildcards extension. Extensions
load by their folder in alphanumeric order.

With the ["Dynamic Prompts" extension](https://github.com/adieyal/sd-dynamic-prompts)
this happens by default due to default folder names for both extensions. But if
this is not the case, you can just rename the extension folder so the ordering
works out.

With the ["AUTOMATIC1111 Wildcards" extension](https://github.com/AUTOMATIC1111/stable-diffusion-webui-wildcards)
you will have to rename one of the folders, so that it loads before than "Send to Negative".

When in doubt, just rename this extension's folder with a "z" in front (for example) so that it is the last one to load, or manually set such folder name when installing it.

## Usage

The format of the tags is like this:

```text
<!content!>
```

And an optional position in the negative prompt can be specified like this:

```text
<!!position!content!>
```

Where position can be:

* s: at the start (the default)
* e: at the end
* pN: at the position of the insertion point "<!!iN!!>" with N being 0-9

If the insertion point is not found it inserts at the start.

## Example

You have a wildcard for hair colors (\_\_haircolors\_\_) with one being
strawberry blonde, but you don't want strawberries. So in that option you add a
tag to add to the negative prompt, like so:

```text
blonde
strawberry blonde <!strawberry!>
brunette
```

Then, if that option is chosen this extension will process it later and move
that part to the negative prompt.

## Configuration

The extension settings allow you to change the format of the tag in case there
is some incompatibility with another extension.

You can also specify the separator added to the negative prompt which by
default is ", ".

By default it ignores repeated content and also tries to clean up the prompt
after removing the tags, but these can also be changed in the settings.
