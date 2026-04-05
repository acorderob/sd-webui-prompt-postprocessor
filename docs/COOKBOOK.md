# Cookbook

This cookbook shows some interesting uses of the features available.

## Wildcard definition

### Grouping

The common use of wildcards is creating multiple of them with simple lists of elements. But this extension supports more interesting ways to group the elements, reducing bloat and improving selection of the wanted elements.

In these examples we assume we want to select colors but we want warm colors to have double weight than cold colors, then have weights for each of them, and we sometimes want to choose only the warm ones, the cold ones, or any of them.

The usual way would be this:

```yaml
colors_warm:
    - 3::red
    - 2::orange
    - 1::yellow
colors_cold:
    - 2::blue
    - 1::green
```

And use `__colors_warm__` or `__colors_cold__`, or `{2::__colors_warm__|1::__colors_cold__}` to get all of them.

The `1` weights are not necessary, it just makes the intent clearer.

#### Filters

You can add labels to the elements of a wildcard, allowing you to reduce the availability to only a subset of them. This avoids the need to create multiple wildcards of similar elements.

```yaml
colors:
    - "'warm'6::red"
    - "'warm'4::orange"
    - "'warm'2::yellow"
    - "'cold'2::blue"
    - "'cold'1::green"
```

And use `__colors'warm'__` or `__colors'cold'__`, or just `__colors__` to get all of them.

Labels can be more complex than this. See the syntax document.

#### Anonymous wildcards

You can also group the elements by using anonymous wildcards, which can also be labeled.

```yaml
colors:
    - "'warm'2":  # this needs double quotes to include the single quotes as part of the options
        - 3::red
        - 2::orange
        - 1::yellow
    - "'cold'1":
        - 2::blue
        - 1::green
```

And use `__colors'warm'__` or `__colors'cold'__`, or just `__colors__` to get all of them.

This produces almost the same effect as before but is easier to read. The only difference is with the weights when you don't filter, because now it first chooses between the warm and the cold options and then the colors inside the chosen one. This allows you to add simpler weights to the two groups and their elements instead of having to calculate the combined weights.

With simple labels this is probably the best method.

#### Wildcard inclusion

Another option, but not as clean, is to include wildcards inside other wildcards.

```yaml
colors_warm:
    - 3::red
    - 2::orange
    - 1::yellow
colors_cold:
    - 2::blue
    - 1::green
colors:
    - "%'warm'2::include colors_warm"
    - "%'cold'1::include colors_cold"
```

Then use `__colors_warm__` or `__colors_cold__`, or `__colors'warm'__` or `__colors'cold'__` or `__colors__` to get all of them.

## Prompt building

You can create a complex set of wildcards that build a full prompt, by using the wildcards along with variables with default values. The variables allow you to choose what parts of the prompt you want to change for specific content, or just leave the defaults. Then, inside the UI, you can use styles (with an appropiate styles node if using ComfyUI) to choose which variables to set. This makes it easy to quickly select what do you want to prompt for.

Wildcards:

```yaml
style:
    realistic: photograph
    oil: oil painting
    sketch: pencil sketch

subject:
    - "'human'::{man|woman}"
    - "'orc,fantasy'::orc"
    - "'goblin,fantasy'::goblin"

clothes:
    - "'regular'::t-shirt, pants, shoes"
    - "'regular'::swimsuit"
    - "'regular'::uniform"
    - "'regular'::pajamas"
    - "'armor'::metal armor"
    - "'armor'::leather armor"

action:
    - "'passive'::standing"
    - "'passive'::sitting"
    - "'passive'::lying down"
    - "'passive'::crouching"
    - "'active'::running"
    - "'active'::dancing"
    - "'active'::driving"

background:
    home:
        - in the kitchen
        - in the bathroom
        - in the living room
    nature:
        - in a forest
        - in a swamp
        - in a desert
        - in a grotto
        - in the beach
    building:
        - in a cathedral
        - in an office
        - in a store
        - in a castle
        - in a dungeon
    any: "{__background/home__|__background/nature__|__background/building__}"

character:
  - "${style:()}, ${subject:__subject'human'__}, ${clothes:__clothes'regular'__}, ${action:__action'passive'__}, ${background:__background/any__}"
```

Styles file:

```csv
name,prompt,negative_prompt
"Nothing","",""
"Style: realistic","${style=__style/realistic__}",""
"Style: oil","${style=__style/oil__}",""
"Style: sketch","${style=__style/sketch__}",""
"Subject: human","${subject=__subject'human'__}",""
"Subject: orc","${subject=__subject'orc'__}",""
"Subject: goblin","${subject=__subject'goblin'__}",""
"Subject: fantasy","${subject=__subject'fantasy'__}",""
"Subject: any","${subject=__subject__}",""
"Clothes: regular","${clothes=__clothes'regular'__}",""
"Clothes: armor","${clothes=__clothes'armor'__}",""
"Clothes: any","${clothes=__clothes__}",""
"Action: passive","${action=__action'passive'__}",""
"Action: active","${action=__action'active'__}",""
"Action: any","${action=__action__}",""
"Background: home","${background=__background/home__}",""
"Background: nature","${background=__background/nature__}",""
"Background: building","${background=__background/building__}",""
"Background: any","${background=__background/any__}",""
"Character","__character__",""
```

You first select the styles that set the variables that you are interested in changing from the default, and you end with the main wildcard that uses them to build the prompt. Note that the order of the variables don't usually matter because they are only evaluated when echoed to the prompt. This allows you to use variables inside wildcards that are inside other variables, and only at the end they will be evaluated.

Sample style selections:

Sample 1:

- "Style: oil"
- "Subject human"
- "Clothes: regular"
- "Background: home"
- "Character"

This would create this prompt:

`${style=__style/oil__}, ${subject=__subject'human'__}, ${clothes=__clothes'regular'__}, ${background=__background/home__}, __character__`

Sample 2:

- "Subject: fantasy"
- "Clothes: armor"
- "Action: active"
- "Background: nature"
- "Character"

This would create this prompt:

`${subject=__subject'fantasy'__}, ${clothes=__clothes'armor'__}, ${action=__action'active'__}, ${background=__background/nature__}, __character__`

## Using variables for detailer prompts

This only applies to ComfyUI, because the variables cannot be used in the ADetailer prompts of the A1111 UIs.

You can put parts of the prompt to be set into variables, and then extract this variables from the output and use them in the prompts of the detailer nodes.

For example, imagine you have this prompt:

`Cyberpunk woman with ${head:long red hair mohawk, green eyes, and neon makeup} riding a futuristic motorcycle`

That will create a variable `head` with the head description and insert it in that position in the prompt. That variable can then be extracted with the "**ACB PPP Select Variable**" node and used as input for the detailer for the head, thus avoiding prompt clutter that does not apply.
