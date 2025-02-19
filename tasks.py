#!/usr/bin/env python3


################################################################################

# Basic usage:
#
# List tasks:
# $ inv --list

"""Misc dev and deployment helper tasks"""

import logging
import os
import subprocess
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional

from colorlog import ColoredFormatter, default_log_colors
from deploykit import DeployHost, HostKeyCheck
from invoke.tasks import task
from tabulate import tabulate

################################################################################

ROOT = Path(__file__).parent.resolve()
os.chdir(ROOT)
LOG = logging.getLogger(os.path.abspath(__file__))

################################################################################


@dataclass(eq=False)
class TargetHost:
    """Represents target host"""

    hostname: str
    port: str
    nixosconfig: str
    secretspath: Optional[str] = None


TARGETS = OrderedDict(
    {
        "jenkins-controller-nixos": TargetHost(
            hostname="127.0.0.1",
            port="2222",
            nixosconfig="jenkins-nixos",
            secretspath="hosts/jenkins-controller/secrets.yaml",
        ),
    }
)


def _get_target(alias: str) -> TargetHost:
    if alias not in TARGETS:
        LOG.fatal("Unknown alias '%s'", alias)
        sys.exit(1)
    return TARGETS[alias]


################################################################################


def set_log_verbosity(verbosity: int = 1) -> None:
    """Set logging verbosity (0=NOTSET, 1=INFO, or 2=DEBUG)"""
    log_levels = [logging.NOTSET, logging.INFO, logging.DEBUG]
    verbosity = min(len(log_levels) - 1, max(verbosity, 0))
    _init_logging(verbosity)


def _init_logging(verbosity: int = 1) -> None:
    """Initialize logging"""
    if verbosity == 0:
        level = logging.NOTSET
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG
    if level <= logging.DEBUG:
        logformat = (
            "%(log_color)s%(levelname)-8s%(reset)s "
            "%(filename)s:%(funcName)s():%(lineno)d "
            "%(message)s"
        )
    else:
        logformat = "%(log_color)s%(levelname)-8s%(reset)s %(message)s"
    default_log_colors["INFO"] = "fg_bold_white"
    default_log_colors["DEBUG"] = "fg_bold_white"
    default_log_colors["SPAM"] = "fg_bold_white"
    formatter = ColoredFormatter(logformat, log_colors=default_log_colors)
    if LOG.hasHandlers() and len(LOG.handlers) > 0:
        stream = LOG.handlers[0]
    else:
        stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    if not LOG.hasHandlers():
        LOG.addHandler(stream)
    LOG.setLevel(level)


# Set logging verbosity (1=INFO, 2=DEBUG)
set_log_verbosity(1)


################################################################################


@task
def alias_list(_c: Any) -> None:
    """
    List available targets (i.e. configurations and alias names)

    Example usage:
    inv list-name
    """
    table_rows = []
    table_rows.append(["alias", "nixosconfig", "hostname", "port"])
    for alias, host in TARGETS.items():
        row = [alias, host.nixosconfig, host.hostname, host.port]
        table_rows.append(row)
    table = tabulate(table_rows, headers="firstrow", tablefmt="fancy_outline")
    print(f"\nCurrent ghaf-infra targets:\n\n{table}")


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
def print_keys(_c: Any, alias: str) -> None:
    """
    Decrypt host private key, print ssh and age public keys for `alias` config.

    Example usage:
    inv print-keys --target binarycache-ficolo
    """
    target = _get_target(alias)
    with TemporaryDirectory() as tmpdir:
        decrypt_host_key(target, tmpdir)
        key = f"{tmpdir}/etc/ssh/ssh_host_ed25519_key"
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


def get_deploy_host(alias: str = "") -> DeployHost:
    """
    Return DeployHost object, given `alias`
    """
    hostname = _get_target(alias).hostname
    port = _get_target(alias).port
    deploy_host = DeployHost(
        host=hostname,
        port=port,
        host_key_check=HostKeyCheck.NONE,
        # verbose_ssh=True,
    )
    return deploy_host


def decrypt_host_key(target: TargetHost, tmpdir: str) -> None:
    """
    Run sops to extract `nixosconfig` secret 'ssh_host_ed25519_key'
    """

    def opener(path: str, flags: int) -> int:
        return os.open(path, flags, 0o400)

    t = Path(tmpdir)
    t.mkdir(parents=True, exist_ok=True)
    t.chmod(0o755)
    host_key = t / "etc/ssh/ssh_host_ed25519_key"
    host_key.parent.mkdir(parents=True, exist_ok=True)
    with open(host_key, "w", opener=opener, encoding="utf-8") as fh:
        try:
            subprocess.run(
                [
                    "sops",
                    "--extract",
                    '["ssh_host_ed25519_key"]',
                    "--decrypt",
                    f"{ROOT}/{target.secretspath}",
                ],
                check=True,
                stdout=fh,
            )
        except subprocess.CalledProcessError:
            LOG.warning(
                "Failed reading secret 'ssh_host_ed25519_key' for '%s'",
                target.nixosconfig,
            )
            ask = input("Still continue? [y/N] ")
            if ask != "y":
                sys.exit(1)
        else:
            pub_key = t / "etc/ssh/ssh_host_ed25519_key.pub"
            with open(pub_key, "w", encoding="utf-8") as fh:
                subprocess.run(
                    ["ssh-keygen", "-y", "-f", f"{host_key}"],
                    stdout=fh,
                    text=True,
                    check=True,
                )
            pub_key.chmod(0o644)


def install_host_key(c: Any, h: DeployHost, alias: str) -> None:
    """
    Install host key
    """
    try:
        h.run(cmd="whoami", stdout=subprocess.PIPE).stdout.strip()
    except subprocess.CalledProcessError:
        LOG.fatal("No ssh access to the remote host")
        sys.exit(1)

    target = _get_target(alias)
    with TemporaryDirectory() as tmpdir:
        decrypt_host_key(target, tmpdir)
        LOG.info("Host key on local tmp:")
        c.run(f"find {tmpdir}")
        h.run(f"mkdir -p /tmp/{tmpdir}")
        cmd = "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        cmd += f"-P {h.port} -r {tmpdir}/* {h.host}:/tmp/{tmpdir}"
        LOG.info("Running: %s", cmd)
        c.run(cmd)
        LOG.info("Copied to remote:")
        h.run(f"find /tmp/{tmpdir}")
        LOG.info("Overwrite ssh host key:")
        h.run(f"sudo mv /tmp/{tmpdir}/etc/ssh/ssh_host_ed25519* /etc/ssh/")
        h.run(f"sudo rm -fr /tmp/{tmpdir}")

    try:
        h.run("sudo reboot now")
        time.sleep(5)
        nix_info = h.run(
            cmd="nix-info; uname -a", stdout=subprocess.PIPE
        ).stdout.strip()
        LOG.info("Remote %s", nix_info)
    except subprocess.CalledProcessError:
        LOG.fatal("No ssh access to the remote host")
        sys.exit(1)


@task
def install_host_keys(c: Any, alias=None) -> None:
    """
    Install host key(s)

    Example usage:
    inv install_host_keys
    inv install_host_keys --alias alias-name-here
    """
    if not alias:
        for _alias, _ in TARGETS.items():
            h = get_deploy_host(_alias)
            install_host_key(c, h, _alias)
    else:
        h = get_deploy_host(alias)
        install_host_key(c, h, alias)
