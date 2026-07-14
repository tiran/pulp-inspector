import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class NpmBuildHook(BuildHookInterface):
    PLUGIN_NAME = "npm-build"

    def initialize(self, version, build_data):
        # sdist includes ui/ source; the frontend is built at wheel time.
        # Editable installs use the Vite dev server, so skip npm build.
        if self.target_name == "sdist" or version == "editable":
            return
        # Install deps from lockfile — needed for isolated builds (e.g.
        # uv build) where the wheel is built from an unpacked sdist
        # without node_modules/.
        subprocess.check_call(["npm", "ci", "--prefix", "ui"])
        # Vite builds into src/pulp_inspector/static/
        subprocess.check_call(["npm", "run", "build", "--prefix", "ui"])
