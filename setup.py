"""Bundle the released evaluator verbatim, including its relative resource paths."""
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

RESOURCES = (
    "scorer/score.py",
    "scorer/prediction_schema.json",
    "prompts/render.py",
    "prompts/zero_shot_messages.json",
    "prompts/few_shot_messages.json",
    "data/splits/split_manifest.json",
    "data/LICENSE",
)


class BuildWithEvaluator(build_py):
    def resource_mapping(self):
        return {str(Path(self.build_lib) / "quasileak" / "_bundled" / name): name for name in RESOURCES}

    def run(self):
        super().run()
        if self.editable_mode:
            return
        for target, source in self.resource_mapping().items():
            self.mkpath(str(Path(target).parent))
            self.copy_file(source, target)

    def get_source_files(self):
        return super().get_source_files() + list(RESOURCES)

    def get_outputs(self, include_bytecode=1):
        return super().get_outputs(include_bytecode) + list(self.resource_mapping())

    def get_output_mapping(self):
        return {**super().get_output_mapping(), **self.resource_mapping()}


setup(cmdclass={"build_py": BuildWithEvaluator})
