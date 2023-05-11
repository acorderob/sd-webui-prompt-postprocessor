# Send To Negative

## Purpose

This extension allows the use of negative weights in the prompt and moves them to the negative prompt. This allows useful tricks when using a wildcard extension since you can add negative parts from the positive prompt. It will process recursive weights (one inside of another), but won't calculate the multiplied weights.

The extension must be loaded after the wildcard extension. With the "Dynamic Prompts" extension this happens by default due to both extensions default folder names.
