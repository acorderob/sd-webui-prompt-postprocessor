import os

requirements_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.txt")

try:
    from modules.launch_utils import requirements_met, run_pip  # A1111

    if not requirements_met(requirements_filename):
        run_pip(f'install -r "{requirements_filename}"', "requirements for Prompt Post-Processor")
except ImportError:
    import launch

    launch.run_pip(f'install -r "{requirements_filename}"', "requirements for Prompt Post-Processor")
