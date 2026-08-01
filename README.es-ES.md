

# Prompt PostProcessor para Stable Diffusion WebUI y ComfyUI

El Prompt PostProcessor (o PPP, anteriormente conocido como "sd-webui-sendtonegative"), es una extensión diseñada para procesar el prompt de varias maneras. Esta extensión es compatible con:

* [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
* [Forge Neo](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo)
* [SD.Next](https://github.com/vladmandic/sdnext)
* [Forge Classic](https://github.com/Haoming02/sd-webui-forge-classic/tree/classic)
* [Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge)
* [reForge](https://github.com/Panchovix/stable-diffusion-webui-reForge)
* [AUTOMATIC1111 Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
* ...y probablemente otros forks

Estas son algunas de sus características:

* Procesa comodines (wildcards). Compatible con la extensión Dynamic Prompts.
* Envía partes del prompt al prompt negativo (la función original de la extensión). Esto permite utilizar trucos útiles al usar comodines, ya que puedes añadir contenido negativo basado en las elecciones realizadas en el prompt positivo.
* Define variantes de modelos (pony, illustrious, ...) y establece estas como variables del sistema, junto con el modelo actual, para detectar cuál se está utilizando.
* Establece y modifica variables de usuario.
* Establece contenido basado en condiciones (como las variables del sistema/usuario).
* Mapea extranetworks (LoRAs) dependiendo de condiciones (como el modelo/variante cargado). Esto te permite añadir LoRAs "virtuales" al prompt que se traducirán al correcto.
* Limpia el prompt eliminando separadores o espacios innecesarios.
* Modo combinatorio.

> [!NOTE]
> Cuando se utiliza en un webui compatible con *A1111*, la extensión debe cargarse después de cualquier otra extensión que modifique el prompt (como otra extensión de comodines).
>
> Normalmente, las extensiones se cargan por el nombre de su carpeta en orden alfanumérico, por lo que si no se cargan en el orden correcto, simplemente cambia el nombre de la carpeta de esta extensión para que el orden sea el adecuado.
>
> En caso de duda, simplemente antepón una "z" al nombre de la carpeta de esta extensión (por ejemplo) para que sea la última en cargarse, o establece manualmente ese nombre de carpeta al instalarla.

Si la extensión se ejecuta antes que otras, como Dynamic Prompts, y la opción "Process wildcards" está habilitada, los comodines serán procesados por PPP y esas extensiones no los obtendrán. Si deshabilitas el procesamiento de comodines y pretendes que otra extensión los procese, debes mantener la opción "What to do with remaining wildcards?" en "ignore".

Notas:

1. Aparte de sus propios comandos, solo reconoce los formatos de prompt estándar de *A1111*. Por lo tanto:

    * **Extra networks**: `<kind:model...>`
    * **Attention**: `[prompt] (prompt) (prompt:weight)`
    * **Alternation**: `[prompt1|prompt2|...]`
    * **Scheduling**: `[prompt1:prompt2:step]`
    * **BREAK**: `prompt1 BREAK prompt2`
    * **Composable Diffusion**: `prompt1:weight1 AND prompt2:weight2`

    *ComfyUI* solo soporta nativamente la atención usando paréntesis, por lo que los que usan corchetes se convertirán. Las demás construcciones no tienen soporte nativo, pero algunos nodos personalizados las implementan. Por ejemplo:
        [ComfyUI_smZNodes](https://github.com/shiimizu/ComfyUI_smZNodes)

    También recomiendo un nodo para añadir LoRAs desde el prompt, como:
        [LoRA Tag Loader for ComfyUI](https://github.com/badjeff/comfyui_lora_tag_loader)

    En *SD.Next* esto significa que solo los analizadores (parsers) *A1111* o *Full* son compatibles. Te advertirá si usas el analizador *Compel*.
    No reconoce separadores de tokenizador como `TE2:` y `TE3:`, por lo que enviar contenido al prompt negativo desde esas secciones del prompt no lo añadirá en la sección correspondiente del prompt negativo.

2. Reconoce comodines en los formatos `__wildcard__` y {choice|choice} (y casi todo lo que soporta [Dynamic Prompts](https://github.com/adieyal/sd-dynamic-prompts)).
3. No crea construcciones *AND/BREAK* al mover contenido al prompt negativo.

## Instalación

En *ComfyUI*:

1. Ve a Manager > Custom Nodes Manager
2. Busca "Prompt PostProcessor" e instala, o haz clic en Install via Git URL e introduce <https://github.com/acorderob/sd-webui-prompt-postprocessor>
3. Reinicia

En webuis compatibles con *A1111*:

1. Ve a Extensions > Install from URL
2. Pega <https://github.com/acorderob/sd-webui-prompt-postprocessor> en el campo de texto URL for extension's git repository
3. Haz clic en el botón Install
4. Reinicia el webui

En *SD.Next* te recomiendo deshabilitar el procesamiento nativo de comodines y usar la interfaz de usuario antigua (old UI).

## Configuración

Consulta la [documentación de configuración](docs/CONFIG.md).

## Uso

Consulta la [documentación de sintaxis](docs/SYNTAX.md).

## Recetario (Cookbook)

Consulta el [recetario](docs/COOKBOOK.md) para ver usos interesantes.

## Herramientas

Existe una herramienta `tools/convert_styles.py` para convertir estilos de A1111 o SD.Next en un archivo de comodines.

## Contribuir

Para desarrollar, sugiero hacerlo con la extensión aislada de la interfaz de usuario (puedes usar un enlace simbólico para probarla en la UI), y con su propio entorno virtual (venv o .venv), para que las pruebas funcionen y se puedan depurar correctamente.

## Licencia

MIT

## Contacto

Si tienes alguna pregunta o inquietud, por favor inicia un hilo en las discusiones. Para reportar errores o solicitar características, abre un issue.
