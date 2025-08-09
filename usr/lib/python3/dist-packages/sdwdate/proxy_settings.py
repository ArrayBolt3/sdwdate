#!/usr/bin/python3 -su

# Copyright (C) 2017 - 2025 ENCRYPTED SUPPORT LLC <adrelanos@whonix.org>
# See the file COPYING for copying conditions.

import sys

sys.dont_write_bytecode = True

import os
import glob
import re
from subprocess import check_output


def proxy_settings() -> tuple[str, str]:
    current_ip_address: str = "127.0.0.1"
    current_port_number: str = "9050"
    settings_path: str = "/usr/libexec/helper-scripts/settings_echo"

    if os.path.exists("/usr/share/whonix") and os.access(
        settings_path, os.X_OK
    ):
        ip_address_bytes_match: re.Match[bytes] | None
        ip_address_str_match: re.Match[str] | None
        port_str_match: re.Match[str] | None

        proxy_settings_bytes: bytes = check_output(settings_path)
        ip_address_bytes_match = re.search(b'GATEWAY_IP="(.*)"', proxy_settings_bytes)
        if ip_address_bytes_match is None:
            return "", ""
        current_ip_address = (
            ip_address_bytes_match.group(1).decode()
        )

    if os.path.exists("/usr/share/whonix"):
        current_port_number = "9108"

    if os.path.exists("/etc/sdwdate.d/"):
        files: list[str] = sorted(glob.glob("/etc/sdwdate.d/*.conf"))
        for f in files:
            with open(f) as conf:
                lines: list[str] = conf.readlines()
            for line in lines:
                if line.startswith("PROXY_IP"):
                    ip_address_str_match = re.search(r"=(.*)", line)
                    if ip_address_str_match is None:
                        return "", ""
                    current_ip_address = ip_address_str_match.group(1)
                if line.startswith("PROXY_PORT"):
                    port_str_match = re.search(r"=(.*)", line)
                    if port_str_match is None:
                        return "", ""
                    current_port_number = port_str_match.group(1)

    return current_ip_address, current_port_number


if __name__ == "__main__":
    ip_address: str
    port_number: str
    ip_address, port_number = proxy_settings()
    print(f"{ip_address} {port_number}")
