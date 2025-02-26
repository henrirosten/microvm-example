#!/usr/bin/env python3


################################################################################

# Basic usage:
#
# List tasks:
# $ inv --list

"""Misc dev and deployment helper tasks"""

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from invoke.tasks import task

################################################################################

ROOT = Path(__file__).parent.resolve()
os.chdir(ROOT)

SECRET_PATHS = {
    "jenkins-controller": "hosts/jenkins-controller/secrets.yaml",
}

################################################################################


@task
def update_sops_files(c: Any) -> None:
    """
    Update all sops yaml and json files according to .sops.yaml rules.

    Example usage:
    inv update-sops-files
    """
    c.run(
        r"""
find . \
        -type f \
        \( -iname '*.enc.json' -o -iname 'secrets.yaml' \) \
        -exec sops updatekeys --yes {} \;
"""
    )


@task
def print_keys(_c: Any, name: str) -> None:
    """
    Decrypt host private key, print ssh and age public keys for `name` config.
    """
    with TemporaryDirectory() as tmpdir:
        decrypt_host_key(name, tmpdir)
        key = f"{tmpdir}/ssh_host_ed25519_key"
        pubkey = subprocess.run(
            ["ssh-keygen", "-y", "-f", f"{key}"],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        print("###### Public keys ######")
        print(pubkey.stdout)
        print("###### Age keys ######")
        subprocess.run(
            ["ssh-to-age"],
            input=pubkey.stdout,
            check=True,
            text=True,
        )


@task
def install_host_key(_c: Any, name: str) -> None:
    """
    Install host key for 'name' config
    """
    _secretspath = SECRET_PATHS[name]
    tmpdir = f"/tmp/shared/{name}"
    subprocess.run(["rm", "-f", "-r", tmpdir], check=True, text=True,)
    path = decrypt_host_key(name, tmpdir)
    print(f"[+] Decrypted host key at: {path}")


def decrypt_host_key(name: str, tmpdir: str) -> Path:
    """
    Run sops to extract secret 'ssh_host_ed25519_key'
    """

    def opener(path: str, flags: int) -> int:
        return os.open(path, flags, 0o400)

    secretspath = SECRET_PATHS[name]
    t = Path(tmpdir)
    t.mkdir(parents=True, exist_ok=True)
    t.chmod(0o755)
    host_key = t / "ssh_host_ed25519_key"
    host_key.parent.mkdir(parents=True, exist_ok=True)
    with open(host_key, "w", opener=opener, encoding="utf-8") as fh:
        try:
            subprocess.run(
                [
                    "sops",
                    "--extract",
                    '["ssh_host_ed25519_key"]',
                    "--decrypt",
                    f"{ROOT}/{secretspath}",
                ],
                check=True,
                stdout=fh,
            )
        except subprocess.CalledProcessError:
            print(f"Failed reading secret 'ssh_host_ed25519_key' for '{name}'")
            ask = input("Still continue? [y/N] ")
            if ask != "y":
                sys.exit(1)
    return host_key
