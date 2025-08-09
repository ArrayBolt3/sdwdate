#!/usr/bin/python3 -su

# Copyright (C) 2015 troubadour <trobador@riseup.net>
# Copyright (C) 2015 - 2025 ENCRYPTED SUPPORT LLC <adrelanos@whonix.org>
# See the file COPYING for copying conditions.

# Example:
# sudo -u sdwdate python3 /usr/lib/python3/dist-packages/sdwdate/remote_times.py "http://www.dds6qkxpwdeubwucdiaord2xgbbeyds25rbsgr73tbfpqpt4a6vjwsyd.onion/a http://www.dds6qkxpwdeubwucdiaord2xgbbeyds25rbsgr73tbfpqpt4a6vjwsyd.onion/b http://www.dds6qkxpwdeubwucdiaord2xgbbeyds25rbsgr73tbfpqpt4a6vjwsyd.onion/c" "127.0.0.1" "9050"

import sys

sys.dont_write_bytecode = True

import os
import signal
import shlex
import time
import subprocess
from subprocess import Popen, PIPE
import concurrent.futures
from collections import namedtuple
from types import FrameType

from .config import get_comment
from .config import read_pools
from .config import time_human_readable
from .config import time_replay_protection_file_read
from .timesanitycheck import time_consensus_sanity_check
from .timesanitycheck import static_time_sanity_check

class TimeSourcePool(object):
    def __init__(self, pool: int) -> None:
        self.url, self.comment = read_pools(pool, "production")
        self.url_random_pool: list[str] = []
        self.already_picked_index: list[int] = []
        self.done: bool = False


def run_command(
    i: int, url_to_unixtime_command: str
) -> tuple[Popen[bytes], str, float, float, str, str]:
    timeout_seconds: int = 120

    # Avoid Popen shell=True.
    url_to_unixtime_command_list: list[str] = shlex.split(
        url_to_unixtime_command
    )

    start_unixtime: float = time.time()

    process: Popen[bytes] = Popen(
        url_to_unixtime_command_list,
        stdout=PIPE,
        stderr=PIPE,
        text=False,
    )

    status: str
    error_message: str

    try:
        process.wait(timeout_seconds)
        # Process already terminated before timeout.
        print(f"remote_times.py: i: {i} | done")
        status = "done"
    except subprocess.TimeoutExpired:
        print(f"remote_times.py: i: {i} | timeout_network")
        status = "timeout"
        # Timeout hit. Kill process.
        process.kill()
    except BaseException:
        error_message = str(sys.exc_info()[0])
        status = "error"
        print(
            f"remote_times.py: i: {i} | timeout_network unknown error. "
            f"sys.exc_info: {error_message}"
        )
        process.kill()

    # Do not return from this function until killing of the process is
    # complete.
    process.wait()

    end_unixtime: float = time.time()
    took_time: float = end_unixtime - start_unixtime

    # Round took_time to two digits for better readability.
    # No other reason for rounding.
    took_time = round(took_time, 2)

    temp1: bytes = b""
    temp2: bytes = b""

    try:
        # bytes
        temp1, temp2 = process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        print(f"remote_times.py: i: {i} | timeout_read")
        status = "error"
    except BaseException:
        error_message = str(sys.exc_info()[0])
        status = "error"
        print(
            f"remote_times.py: i: {i} | timeout_read unknown error. "
            f"sys.exc_info: {error_message}"
        )
        # No need to use process.kill().
        # Was already terminated by itself or killed above.

    try:
        stdout: str = temp1.decode().strip()
    except BaseException:
        error_message = str(sys.exc_info()[0])
        print(
            f"remote_times.py: i: {i} | stdout decode unknown error. "
            f"sys.exc_info: {error_message}"
        )
        stdout = ""

    try:
        stderr: str = temp2.decode().strip()
    except BaseException:
        error_message = str(sys.exc_info()[0])
        print(
            f"remote_times.py: i: {i} | stderr decode unknown error. "
            f"sys.exc_info: {error_message}"
        )
        stderr = ""

    return process, status, end_unixtime, took_time, stdout, stderr


def check_remote(
    i: int,
    pools: list[TimeSourcePool],
    remote: str,
    process: Popen[bytes],
    status: str,
    end_unixtime: float,
    took_time: float,
    stdout: str,
    stderr: str,
) -> tuple[str, float, float, int, float]:
    message: str = f"remote {i}: {remote}"
    print(message)

    comment: str = get_comment(pools, remote)

    message = f"* comment: {comment}"
    print(message)

    half_took_time_float: float = took_time / 2
    # Round took_time to two digits for better readability.
    # No other reason for rounding.
    half_took_time_float = round(half_took_time_float, 2)

    message = f"* took_time     : {took_time} second(s)"
    print(message)
    message = f"* half_took_time: {half_took_time_float} second(s)"
    print(message)

    unixtime_maybe: str = stdout

    stdout_string_length: int = len(stdout)
    unixtime_string_length_max: int = 10

    if stdout_string_length == 0:
        stdout = "empty"
        if not status == "timeout":
            status = "error"
    else:
        if not stdout_string_length == unixtime_string_length_max:
            status = "error"
            print(
                "* ERROR: stdout unexpected string length: "
                f"{stdout_string_length}"
            )

    if not status == "timeout":
        if not process.returncode == 0:
            status = "error"

    stderr_string_length: int = len(stderr)
    stderr_string_length_max: int = 500

    if stderr_string_length == 0:
        stderr = "empty"

    if stderr_string_length > stderr_string_length_max:
        status = "error"
        print(
            "* ERROR: stderr excessive string length: "
            f"{stderr_string_length}"
        )

    # Test:
    # status = "done"

    remote_unixtime: int = 0

    if status not in ("timeout", "error"):
        try:
            # cast str unixtime_maybe to int remote_unixtime
            remote_unixtime = int(unixtime_maybe)
        except BaseException:
            status = "error"
            error_message: str = str(sys.exc_info()[0])
            print(
                "* ERROR: Could not cast to int. error_message: "
                f"{error_message}"
            )

        # Test:
        # remote_unixtime = 99999999999999999999
        # remote_unixtime = -1
        # remote_unixtime = 1
        # status = "done"

        # Simple test if above cast str unixtime_maybe to int remote_unixtime
        # was a success. Within 1 and 999999999. Just to make sure to not
        # continue with excessively larger numbers. A better time sanity test
        # is being done later below.
        remote_unixtime_max: int = 9999999999
        remote_unixtime_min: int = 0
        if remote_unixtime > remote_unixtime_max:
            status = "error"
            print("* ERROR: remote_unixtime(int) too large!")
        if remote_unixtime <= remote_unixtime_min:
            status = "error"
            print("* ERROR: remote_unixtime(int) smaller or equal 0!")

    if not status == "done":
        message = f"* exit_code: {process.returncode}"
        print(message)
        if not stdout_string_length > unixtime_string_length_max:
            message = f"* stdout: {stdout}"
            print(message)
        if not stderr_string_length > stderr_string_length_max:
            message = f"* stderr: {stderr}"
            print(message)
        message = f"* remote_status: {status}"
        print(message)
        remote_unixtime = 0
        time_diff_raw_int: int = 0
        time_diff_lag_cleaned_float: float = 0.0
        return (
            status,
            half_took_time_float,
            remote_unixtime,
            time_diff_raw_int,
            time_diff_lag_cleaned_float,
        )

    time_diff_raw_int = int(remote_unixtime) - int(end_unixtime)
    remote_time: str = time_human_readable(remote_unixtime)

    # 1. User's sdwdate sends request to remote time source.
    # 2. Server creates reply (HTTP DATE header).
    # 3. Server sends reply back to user's sdwdate.
    # Therefore assume that half of the time required to get the time
    # reply has to be deducted from the raw time diff.
    time_diff_lag_cleaned_float = (
        float(time_diff_raw_int) - half_took_time_float
    )
    time_diff_lag_cleaned_float = round(time_diff_lag_cleaned_float, 2)

    time_replay_protection_minimum_unixtime_int: int
    time_replay_protection_minimum_unixtime_human_readable: str
    (
        time_replay_protection_minium_unixtime_int,
        time_replay_protection_minium_unixtime_human_readable,
    ) = time_replay_protection_file_read()

    time_replay_protection_minium_unixtime_human_readable = (
        time_replay_protection_minium_unixtime_human_readable.strip()
    )

    time_replay_protection_minium_unixtime_str: str = str(
        time_replay_protection_minium_unixtime_int
    )

    timesanitycheck_status_static: str
    timesanitycheck_error_static: str
    (timesanitycheck_status_static, timesanitycheck_error_static) = (
        static_time_sanity_check(remote_unixtime)
    )

    consensus_status: str
    consensus_error: str
    consensus_valid_after_str: str
    consensus_valid_until_str: str
    (
        consensus_status,
        consensus_error,
        consensus_valid_after_str,
        consensus_valid_until_str,
    ) = time_consensus_sanity_check(remote_unixtime)

    message = (
        "* replay_protection_unixtime: "
        f"{time_replay_protection_minium_unixtime_str}"
    )
    print(message)
    message = f"* remote_unixtime           : {remote_unixtime}"
    print(message)

    message = (
        "* consensus/valid-after           : " f"{consensus_valid_after_str}"
    )
    print(message)
    message = (
        "* replay_protection_time          : "
        f"{time_replay_protection_minium_unixtime_human_readable}"
    )
    print(message)
    message = f"* remote_time                     : {remote_time}"
    print(message)
    message = (
        "* consensus/valid-until           : " f"{consensus_valid_until_str}"
    )
    print(message)

    message = "* time_diff_raw        : " f"{time_diff_raw_int} second(s)"
    print(message)
    message = (
        f"* time_diff_lag_cleaned: {time_diff_lag_cleaned_float} second(s)"
    )
    print(message)

    # Fallback.
    remote_status: bool | None = None

    if timesanitycheck_status_static == "sane":
        message = "* Time Replay Protection         : sane"
        print(message)
    elif timesanitycheck_status_static == "slow":
        message = "* Time Replay Protection         : slow"
        print(message)
        remote_status = False
    elif timesanitycheck_status_static == "fast":
        message = "* Time Replay Protection         : fast"
        print(message)
        remote_status = False
    elif timesanitycheck_status_static == "error":
        message = (
            "* Static Time Sanity Check       : error:"
            + timesanitycheck_error_static
        )
        print(message)
        remote_status = False

    if consensus_status == "ok":
        message = "* Tor Consensus Time Sanity Check: sane"
        print(message)
        if not remote_status == False:
            remote_status = True
    elif consensus_status == "slow":
        message = "* Tor Consensus Time Sanity Check: slow"
        print(message)
        remote_status = False
    elif consensus_status == "fast":
        message = "* Tor Consensus Time Sanity Check: fast"
        print(message)
        remote_status = False
    elif consensus_status == "error":
        message = "* Tor Consensus Time Sanity Check: error: " + consensus_error
        print(message)
        remote_status = False

    message = f"* remote_status: {remote_status}"
    print(message)

    if remote_status:
        status = "ok"
        return (
            status,
            half_took_time_float,
            remote_unixtime,
            time_diff_raw_int,
            time_diff_lag_cleaned_float,
        )

    remote_unixtime = 0
    time_diff_raw_int = 0
    time_diff_lag_cleaned_float = 0.00
    return (
        status,
        half_took_time_float,
        remote_unixtime,
        time_diff_raw_int,
        time_diff_lag_cleaned_float,
    )


def get_time_from_servers(
    pools: list[TimeSourcePool],
    list_of_remote_servers: list[str],
    proxy_ip_address: str,
    proxy_port_number: str,
) -> tuple[
    list[str],
    list[str],
    list[float],
    list[float],
    list[float],
    list[int],
    list[float],
]:
    number_of_remote_servers: int = len(list_of_remote_servers)
    # Example number_of_remote_servers:
    # 3
    range_of_remote_servers: range = range(number_of_remote_servers)
    # Example range_of_remote_servers:
    # range(0, 3)

    url_to_unixtime_debug: str = "true"

    run_command_status: str
    check_remote_status: str
    half_took_time: float
    remote_unixtime: float
    handle: Popen[bytes]
    future: concurrent.futures.Future[
        tuple[Popen[bytes], str, float, float, str, str]
    ]

    end_unixtime: float
    took_time: float
    stdout: str
    stderr: str

    time_diff_raw_int: int
    time_diff_lag_cleaned_float: float

    url_to_unixtime_command: str

    run_command_status_list: list[str] = []
    check_remote_status_list: list[str] = []
    url_list: list[str] = []
    half_took_time_list: list[float] = []
    remote_unixtime_list: list[float] = []
    handle_list: list[Popen[bytes]] = []
    future_list: list[
        concurrent.futures.Future[
            tuple[Popen[bytes], str, float, float, str, str]
        ]
    ] = []
    end_unixtime_list: list[float] = []
    took_time_list: list[float] = []
    stdout_list: list[str] = []
    stderr_list: list[str] = []
    time_diff_raw_int_list: list[int] = []
    time_diff_lag_cleaned_float_list: list[float] = []
    url_to_unixtime_command_list: list[str] = []

    print("remote_times.py: url_to_unixtime_command (s):")
    for i in range_of_remote_servers:
        url_to_unixtime_command = (
            f"url_to_unixtime {proxy_ip_address} {proxy_port_number} "
            f"{list_of_remote_servers[i]}  {url_to_unixtime_debug}"
        )
        url_to_unixtime_command_list.append(url_to_unixtime_command)
        print(url_to_unixtime_command_list[i])

    print("")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        for i in range_of_remote_servers:
            future_list.append(
                executor.submit(run_command, i, url_to_unixtime_command_list[i])
            )

    for i in range_of_remote_servers:
        (
            handle,
            run_command_status,
            end_unixtime,
            took_time,
            stdout,
            stderr,
        ) = future_list[i].result()
        handle_list.append(handle)
        run_command_status_list.append(run_command_status)
        end_unixtime_list.append(end_unixtime)
        took_time_list.append(took_time)
        stdout_list.append(stdout)
        stderr_list.append(stderr)

    for i in range_of_remote_servers:
        assert stdout_list[i] is not None
        assert stderr_list[i] is not None

        (
            check_remote_status,
            half_took_time,
            remote_unixtime,
            time_diff_raw_int,
            time_diff_lag_cleaned_float,
        ) = check_remote(
            i,
            pools,
            list_of_remote_servers[i],
            handle_list[i],
            run_command_status_list[i],
            end_unixtime_list[i],
            took_time_list[i],
            stdout_list[i],
            stderr_list[i],
        )
        check_remote_status_list.append(check_remote_status)
        half_took_time_list.append(half_took_time)
        remote_unixtime_list.append(remote_unixtime)
        time_diff_raw_int_list.append(time_diff_raw_int)
        time_diff_lag_cleaned_float_list.append(time_diff_lag_cleaned_float)

        print("")

        url_list.append(list_of_remote_servers[i])

    print("remote_times.py: url_list:")
    print(str(url_list))
    print("remote_times.py: check_remote_status_list:")
    print(str(check_remote_status_list))
    print("remote_times.py: took_time_list:")
    print(str(took_time_list))
    print("remote_times.py: half_took_time_list:")
    print(str(half_took_time_list))
    print("remote_times.py: remote_unixtime_list:")
    print(str(remote_unixtime_list))
    print("remote_times.py: time_diff_raw_int_list:")
    print(str(time_diff_raw_int_list))
    print("remote_times.py: time_diff_lag_cleaned_float_list:")
    print(str(time_diff_lag_cleaned_float_list))

    return (
        url_list,
        check_remote_status_list,
        remote_unixtime_list,
        took_time_list,
        half_took_time_list,
        time_diff_raw_int_list,
        time_diff_lag_cleaned_float_list,
    )


# pylint: disable=unused-argument
def remote_times_signal_handler(sig: int, frame: FrameType | None) -> None:
    print("remote_times_signal_handler: OK")
    sys.exit(128 + sig)


def main() -> None:
    os.environ["LC_TIME"] = "C"
    os.environ["TZ"] = "UTC"
    time.tzset()

    signal.signal(signal.SIGTERM, remote_times_signal_handler)
    signal.signal(signal.SIGINT, remote_times_signal_handler)

    pools: list[TimeSourcePool] = []
    number_of_pools: int = 3
    pool_range: range = range(number_of_pools)
    for pool_item in pool_range:
        pools.append(TimeSourcePool(pool_item))

    list_of_remote_servers: list[str] = sys.argv[1].split()
    proxy_ip_address: str = sys.argv[2]
    proxy_port_number: str = sys.argv[3]

    get_time_from_servers(
        pools, list_of_remote_servers, proxy_ip_address, proxy_port_number
    )


if __name__ == "__main__":
    main()
