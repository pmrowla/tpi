import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional

from funcy import first

from .base import BaseMachineBackend

logger = logging.getLogger(__name__)


class TerraformBackend(BaseMachineBackend):
    @contextmanager
    def make_tf(self, name: str):
        from dvc.tpi import DvcTerraform, TerraformError
        from dvc.utils.fs import makedirs

        try:
            working_dir = os.path.join(self.tmp_dir, name)
            makedirs(working_dir, exist_ok=True)
            yield DvcTerraform(working_dir=working_dir)
        except TerraformError:
            raise
        except Exception as exc:
            raise TerraformError("terraform failed") from exc

    def create(self, name: Optional[str] = None, **config):
        from dvc.tpi import render_json
        from python_terraform import IsFlagged

        assert name and "cloud" in config
        with self.make_tf(name) as tf:
            tf_file = os.path.join(tf.working_dir, "main.tf.json")
            with open(tf_file, "w", encoding="utf-8") as fobj:
                fobj.write(render_json(name=name, **config, indent=2))
            tf.cmd("init")
            tf.cmd("apply", auto_approve=IsFlagged)

    def destroy(self, name: Optional[str] = None, **config):
        from python_terraform import IsFlagged

        assert name

        with self.make_tf(name) as tf:
            if first(tf.iter_instances(name)):
                tf.cmd("destroy", auto_approve=IsFlagged)

    def instances(self, name: Optional[str] = None, **config) -> Iterator[dict]:
        assert name

        with self.make_tf(name) as tf:
            yield from tf.iter_instances(name)

    def _default_resource(self, name):
        from dvc.tpi import TerraformError

        resource = first(self.instances(name))
        if not resource:
            raise TerraformError(f"No active '{name}' instances")
        return resource

    def run_shell(self, name: Optional[str] = None, **config):
        from dvc.tpi import DvcTerraform

        resource = self._default_resource(name)
        with DvcTerraform.pemfile(resource) as pem:
            self._shell(
                host=resource["instance_ip"],
                username="ubuntu",
                client_keys=pem,
                known_hosts=None,
            )