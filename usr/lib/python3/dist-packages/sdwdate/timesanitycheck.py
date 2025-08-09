#!/usr/bin/python3 -su

# Copyright (C) 2017 - 2025 ENCRYPTED SUPPORT LLC <adrelanos@whonix.org>
# See the file COPYING for copying conditions.

# sudo -u sdwdate
# python3 /usr/lib/python3/dist-packages/sdwdate/timesanitycheck.py 1611640486

import sys

sys.dont_write_bytecode = True

import os
import time

# from datetime import datetime
from dateutil.parser import parse
from stem.connection import connect  # type: ignore
from typing import Any
import subprocess

os.environ["LC_TIME"] = "C"
os.environ["TZ"] = "UTC"
time.tzset()


def time_consensus_sanity_check(
    target_unixtime: int,
) -> tuple[str, str, str, str]:
    current_error: str = ""
    current_status: str = "ok"
    consensus_valid_after_str: str = ""
    consensus_valid_until_str: str = ""

    try:
        controller: Any = connect()
        if controller is None:
            raise ValueError()
    except BaseException:
        current_status = "error"
        current_error = (
            "Could not open Tor control connection. error: "
            f"{str(sys.exc_info()[0])}"
        )
        return (
            current_status,
            current_error,
            consensus_valid_after_str,
            consensus_valid_until_str,
        )

    assert controller is not None

    try:
        consensus_valid_after_str = controller.get_info("consensus/valid-after")
        consensus_valid_until_str = controller.get_info("consensus/valid-until")
    except BaseException:
        current_status = "error"
        current_error = (
            "Could not request from Tor control connection. error: "
            f"{str(sys.exc_info()[0])}"
        )
        return (
            current_status,
            current_error,
            consensus_valid_after_str,
            consensus_valid_until_str,
        )

    try:
        controller.close()
    except BaseException:
        pass

    try:
        consensus_valid_after_unixtime: str = parse(
            consensus_valid_after_str
        ).strftime("%s")
        consensus_valid_until_unixtime: str = parse(
            consensus_valid_until_str
        ).strftime("%s")

        if target_unixtime > int(consensus_valid_after_unixtime):
            pass
        else:
            current_status = "slow"

        if target_unixtime > int(consensus_valid_until_unixtime):
            current_status = "fast"
        else:
            pass
    except BaseException:
        try:
            controller.close()
        except BaseException:
            pass
        current_error = f"Unexpected error: {str(sys.exc_info()[0])}"
        current_status = "error"

    return (
        current_status,
        current_error,
        consensus_valid_after_str,
        consensus_valid_until_str,
    )


def static_time_sanity_check(unixtime_to_validate: int) -> tuple[str, str]:
    # Tue, 17 May 2033 10:00:00 GMT
    expiration_unixtime: int = 1999936800
    # expiration_time = datetime.strftime(
    # datetime.fromtimestamp(expiration_unixtime),
    # '%a %b %d %H:%M:%S UTC %Y')

    try:
        # time_to_validate_human_readable = datetime.strftime(
        # datetime.fromtimestamp(unixtime_to_validate), '%a %b %d %H:%M:%S UTC
        # %Y')

        p: subprocess.Popen[bytes] = subprocess.Popen(
            "/usr/bin/minimum-unixtime-show",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        stdout: bytes
        stderr: bytes
        stdout, stderr = p.communicate()

        minimum_unixtime: int = int(stdout.decode())
        # minimum_time_human_readable = stderr.decode()

        current_status: str
        current_error: str

        if unixtime_to_validate < minimum_unixtime:
            current_status = "slow"
        elif unixtime_to_validate > expiration_unixtime:
            current_status = "fast"
        else:
            current_status = "sane"

        current_error = "none"

        return current_status, current_error
    except BaseException:
        current_status = "error"
        current_error = str(sys.exc_info()[0])
        return current_status, current_error


if __name__ == "__main__":
    unixtime: int = int(sys.argv[1])
    time_consensus_sanity_check(unixtime)
    status: str
    error: str
    status, error = static_time_sanity_check(unixtime)
    print("status: " + status)
    print("error: " + error)
