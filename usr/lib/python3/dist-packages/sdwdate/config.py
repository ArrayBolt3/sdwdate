#!/usr/bin/python3 -su

# Copyright (C) 2017 - 2025 ENCRYPTED SUPPORT LLC <adrelanos@whonix.org>
# See the file COPYING for copying conditions.

# python3 /usr/lib/python3/dist-packages/sdwdate/config.py 0 test
# python3 /usr/lib/python3/dist-packages/sdwdate/config.py 1 test
# python3 /usr/lib/python3/dist-packages/sdwdate/config.py 2 test
##
# python3 /usr/lib/python3/dist-packages/sdwdate/config.py 0 production
# python3 /usr/lib/python3/dist-packages/sdwdate/config.py 1 production
# python3 /usr/lib/python3/dist-packages/sdwdate/config.py 2 production

import sys

sys.dont_write_bytecode = True

import os
import sys
import glob
import re
import random
import subprocess
from datetime import datetime

from .remote_times import TimeSourcePool


def time_human_readable(unixtime: int) -> str:
    human_readable_unixtime: str = datetime.strftime(
        datetime.fromtimestamp(unixtime), "%Y-%m-%d %H:%M:%S"
    )
    return human_readable_unixtime


def time_replay_protection_file_read() -> tuple[int, str]:
    process: subprocess.Popen[bytes] = subprocess.Popen(
        "/usr/bin/minimum-unixtime-show",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    stdout: bytes
    stderr: bytes
    stdout, stderr = process.communicate()
    unixtime: int = int(stdout)
    time_human_readable_str: str = stderr.decode("utf-8").strip()
    # Relay check to avoid false-positives due to sdwdate inaccuracy.
    unixtime = unixtime - 100
    return unixtime, time_human_readable_str


def randomize_time_config() -> bool:
    status: bool = False
    if not os.path.exists("/etc/sdwdate.d/"):
        return status
    files: list[str] = sorted(glob.glob("/etc/sdwdate.d/*.conf"))
    for file_item in files:
        with open(file_item) as conf:
            lines: list[str] = conf.readlines()
            for line in lines:
                if line.startswith("RANDOMIZE_TIME=true"):
                    status = True
                if line.startswith("RANDOMIZE_TIME=false"):
                    status = False
    return status


def allowed_failures_config() -> float:
    failure_ratio: float | None = None
    if os.path.exists("/etc/sdwdate.d/"):
        files: list[str] = sorted(glob.glob("/etc/sdwdate.d/*.conf"))
        for file_item in files:
            with open(file_item) as conf:
                lines: list[str] = conf.readlines()
            for line in lines:
                if line.startswith("MAX_FAILURE_RATIO"):
                    try:
                        failure_match: re.Match[str] | None = re.search(
                            r"=(.*)", line
                        )
                        if failure_match is None:
                            raise ValueError()
                        failure_ratio = float(failure_match.group(1))
                    except ValueError:
                        print(f"Invalid configuration line '{line}' found")
    if failure_ratio is None:
        failure_ratio = 0.34
    return failure_ratio


def allowed_failures_calculate(
    failure_ratio: float,
    pools_total_number: int,
    number_of_pool_members: int,
) -> int:
    temp: float = float(number_of_pool_members) * failure_ratio
    allowed_failures_value: int = int(temp / float(pools_total_number))
    return allowed_failures_value


def get_comment(pools: list[TimeSourcePool], remote: str) -> str:
    """For logging the comments, get the index of the url
    to get it from pool.comment.
    """
    url_comment: str = "unknown-comment"
    for pool_item in pools:
        try:
            url_index = pool_item.url.index(remote)
            url_comment = pool_item.comment[url_index]
            break
        except BaseException:
            pass
    return url_comment


def get_comment_pool_single(
    target_pool: tuple[list[str], list[str]], remote: str
) -> str:
    url_comment: str = "unknown-comment"
    try:
        url_index = target_pool[0].index(remote)
        url_comment = target_pool[1][url_index]
    except BaseException:
        pass
    return url_comment


def sort_pool(
    target_pool: list[str],
    target_mode: str,
) -> tuple[list[str], list[str]]:
    # Check number of multi-line pool.
    number_of_pool_multi: int = 0
    for i in range(len(target_pool)):
        if target_pool[i] == "[":
            number_of_pool_multi += 1

    # Dynamically create multi-line lists.
    multi_list_url: list[list[str]] = [[] for _ in range(number_of_pool_multi)]
    multi_list_comment: list[list[str]] = [
        [] for _ in range(number_of_pool_multi)
    ]

    # Sort...
    multi_line: bool = False
    multi_index: int = 0
    pool_single_url: list[str] = []
    pool_single_comment: list[str] = []

    url: re.Match[str] | None
    comment: re.Match[str] | None

    for i in range(len(target_pool)):
        if multi_line and target_pool[i] == "]":
            multi_line = False
            multi_index = multi_index + 1

        elif multi_line and target_pool[i].startswith('"'):
            url = re.search(r'"(.*)#', target_pool[i])
            if url is not None:
                if target_mode == "production":
                    multi_list_url[multi_index].append(url.group(1).strip())
                elif target_mode == "test":
                    pool_single_url.append(url.group(1).strip())
            comment = re.search(r'#(.*)"', target_pool[i])
            if comment is not None:
                if target_mode == "production":
                    multi_list_comment[multi_index].append(
                        comment.group(1).strip()
                    )
                elif target_mode == "test":
                    pool_single_comment.append(comment.group(1).strip())

        elif target_pool[i] == "[":
            multi_line = True

        elif target_pool[i].startswith('"'):
            url = re.search(r'"(.*)#', target_pool[i])
            if url is not None:
                pool_single_url.append(url.group(1).strip())
            comment = re.search(r'#(.*)"', target_pool[i])
            if comment is not None:
                pool_single_comment.append(comment.group(1).strip())

    # Pick a random url in each multi-line pool,
    # append it to single url pool.
    for i in range(number_of_pool_multi):
        if target_mode == "production":
            single_ulr_index: int = random.sample(
                range(len(multi_list_url[i])), 1
            )[0]
            single_url: str = multi_list_url[i][single_ulr_index]
            single_comment: str = multi_list_comment[i][single_ulr_index]
            pool_single_url.append(single_url)
            pool_single_comment.append(single_comment)

    return pool_single_url, pool_single_comment


def read_pools(
    target_pool: int, target_mode: str
) -> tuple[list[str], list[str]]:
    in_sdwdate_pool_zero: bool = False
    in_sdwdate_pool_one: bool = False
    in_sdwdate_pool_two: bool = False

    pool_one: list[str] = []
    pool_two: list[str] = []
    pool_three: list[str] = []

    if os.path.exists("/etc/sdwdate.d/"):
        files: list[str] = sorted(glob.glob("/etc/sdwdate.d/*.conf"))

        if files:
            conf_found: bool = False
            for conf in files:
                conf_found = True
                with open(conf) as c:
                    for line in c:
                        line = line.strip()
                        if line.startswith("SDWDATE_POOL_ZERO"):
                            in_sdwdate_pool_zero = True

                        elif line.startswith("SDWDATE_POOL_ONE"):
                            in_sdwdate_pool_zero = False
                            in_sdwdate_pool_one = True

                        elif line.startswith("SDWDATE_POOL_TWO"):
                            in_sdwdate_pool_zero = False
                            in_sdwdate_pool_one = False
                            in_sdwdate_pool_two = True

                        elif in_sdwdate_pool_zero and not line.startswith("##"):
                            pool_one.append(line)

                        elif in_sdwdate_pool_one and not line.startswith("##"):
                            pool_two.append(line)

                        elif in_sdwdate_pool_two and not line.startswith("##"):
                            pool_three.append(line)

            if not conf_found:
                print(
                    'No valid file found in user configuration folder "/etc/sdwdate.d".'
                )

        else:
            print(
                'No file found in user configuration folder "/etc/sdwdate.d".'
            )

    else:
        print('User configuration folder "/etc/sdwdate.d" does not exist.')

    pool_one_url: list[str]
    pool_one_comment: list[str]
    pool_two_url: list[str]
    pool_two_comment: list[str]
    pool_three_url: list[str]
    pool_three_comment: list[str]

    pool_one_url, pool_one_comment = sort_pool(pool_one, target_mode)
    pool_two_url, pool_two_comment = sort_pool(pool_two, target_mode)
    pool_three_url, pool_three_comment = sort_pool(pool_three, target_mode)

    read_pool_url: list[list[str]] = [
        pool_one_url,
        pool_two_url,
        pool_three_url,
    ]
    read_pool_comment: list[list[str]] = [
        pool_one_comment,
        pool_two_comment,
        pool_three_comment,
    ]

    return read_pool_url[target_pool], read_pool_comment[target_pool]


if __name__ == "__main__":
    pool: int = int(sys.argv[1])
    mode: str = sys.argv[2]
    pool_url: list[str]
    pool_comment: list[str]
    pool_url, pool_comment = read_pools(pool, mode)
    print("pool: " + str(pool))
    print("pool_url: " + str(pool_url))
    print("pool_comment: " + str(pool_comment))
