from pathlib import Path

requirements_filename = str(Path(__file__).resolve().parent / "requirements.txt")

try:
    from modules.launch_utils import run_pip  # , requirements_met  # A1111
    #if not requirements_met(requirements_filename): # fails in all hosts due to ruamel.yaml or not having specified versions
    run_pip(f'install -r "{requirements_filename}"', "requirements for Prompt Post-Processor")
except ImportError:
    import launch
    launch.run_pip(f'install -r "{requirements_filename}"', "requirements for Prompt Post-Processor")
