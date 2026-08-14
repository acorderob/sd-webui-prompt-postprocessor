# ACB PPP Run Mode Options node

Provides run mode options to the main PPP node.

## Inputs

* **results_limit**: Limit for the number of generated results (except in `single` mode). Important for combinatorial mode.
* **results_shuffle**: It shuffles the results.
* **comb_random_fixed**: If True all specified random samplers will have a fixed value across the combinations.
* **default_sampler**: The default choice sampler when not specified (in non combinatorial mode). Also applies to extranetwork mapping selection.
* **next_seed**: Choose what to do with the seed in the following prompts in `multiple` or `combinatorial` mode. Value can be: `randomize`, `input`, `increment`, `decrement`.

## Outputs

* **options**: The options to send to the PPP node.
