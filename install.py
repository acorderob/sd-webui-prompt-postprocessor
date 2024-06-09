import os
import launch

requirements_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.txt")
launch.run_pip(f'install -r "{requirements_filename}"', "requirements for Prompt Post-Processor")
