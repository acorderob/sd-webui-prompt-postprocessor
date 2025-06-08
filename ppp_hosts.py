from enum import Enum


class SUPPORTED_APPS(Enum):
    comfyui = "comfyui"
    a1111 = "a1111"
    forge = "forge"
    reforge = "reforge"
    sdnext = "sdnext"

SUPPORTED_APPS_NAMES = {
    SUPPORTED_APPS.comfyui: "ComfyUI",
    SUPPORTED_APPS.sdnext: "SD.Next",
    SUPPORTED_APPS.forge: "Forge",
    SUPPORTED_APPS.reforge: "reForge",
    SUPPORTED_APPS.a1111: "A1111 (or compatible)",
}
