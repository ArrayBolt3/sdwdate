<!--
SPDX-FileCopyrightText: ENCRYPTED SUPPORT LLC <adrelanos@kicksecure.com>
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Threat model

## Project summary

sdwdate is a network time synchronization daemon used by Whonix (an
anonymity-focused operating system for general-purpose computing tasks)
and Kicksecure (a security-focused Debian derivative split used as a base
for Whonix). sdwdate obtains the current time by connecting to multiple
untrusted Tor onion services, obtaining the HTTP header timestamps from them,
and normalizing them to a likely-correct current time. This avoids the MITM
vulnerabilities of traditional NTP, uses stronger encryption than NTS, and
bounds the influence of any single compromised or malicious time server:
because the result is the median of the pool, one malicious server cannot move
the time outside the range spanned by the honest servers' offsets, though it
can still shift it within that honest range by supplying an offset that
becomes the median.

## Relevant vulnerability classes:

Any reasonably-mitigatable behavior that may allow a (cooperating group of)
malicious Tor onion service(s) or other Tor network entity/entities to:

* Read data beyond that volunteered by the initial HTTP request,
* Trigger writes to any files on the daemon's machine (aside from temporary
  files used internally to pass time information between components of
  sdwdate),
* Execute remotely provided code of any form on the daemon's machine,
* Stall clock synchronization for an abnormally long time (where "abnormally
  long" is defined as "longer than should be possible given the network I/O
  timeouts present in the code"),
* Cause sdwdate to crash or exit abnormally, or
* Cause sdwdate to trigger any other program to crash or exit abnormally,

is considered a vulnerability. For the first two kinds of vulnerabilities,
severity depends on what kind of data can be read, and where data can be
written. The third and fourth kinds of vulnerabilities are always considered
high- or critical-severity. The fifth and sixth kinds of vulnerability are
considered low-severity if sdwdate (or the process it triggers to misbehave)
is capable of restarting itself automatically and operating normally after
that.

Additionally, reasonably-mitigatable behavior that may allow a *single* Tor
onion service or other Tor network entity to:

* Cause the daemon's machine's clock to be set more than 30 minutes outside of
  the real current time (fast or slow),

is considered a high-severity vulnerability.

Additionally, behavior of any kind that allows a network entity outside of the
Tor network, other than the host and any involved Internet routing hardware and
services, to influence the behavior of sdwdate in any way, is considered a
vulnerability. The severity of the vulnerability is left to the reviewer's
discretion to determine.

Additionally, behavior of any kind that allow a local user to:

* Change the system's time to a user-provided value,
* Read data that their user account would not normally be permitted to read,
* Write to files their user account would not normally be permitted to write,
* Execute user-provided code of any form with the permissions of the sdwdate
  daemon, or
* Escalate their privileges to those of another user,

are considered vulnerabilities. The first, fourth, and fifth kinds of
vulnerabilities are considered high-severify, while the second and third kinds'
severity deepnds on what files can be read and written.

Some behaviors that are explicitly not considered vulnerabilities are:

* Multiple Tor onion services cooperating to cause the daemon's machine's clock
  to be set to an incorrect value (this is unavoidable with sdwdate's
  architecture and is an accepted limitation),
* Any number of Tor onion services stalling clock synchronization for as long
  as network I/O timeouts permit (this also is unavoidable and is an accepted
  limitation).
* Network routing hardware and services permanently stalling time
  synchronization, for instance by refusing to allow the client to connect to
  Tor entry nodes (this is also unavoidable and is an accepted limitation).

## Dependency context and scope of review

Many references to `helper-scripts` will be seen throughout the code. This is a
collection of utilities for Whonix and Kicksecure, with wildly varying use cases.
While the source code of these components are provided at `/opt/helper-scripts`
for reference and to allow reviewers to run sdwdate, these components are out
of scope for review except inasmuch as they have a direct effect on sdwdate.
Reviewers must not review helper-scripts files if possible.

Reviewers will also see references to `leaprun` and `privleapd`. These are
components of `privleap`, a privilege escalation utility similar in utility to
`sudo`. `privleapd` is an underlying daemon whose inner workings are not
relevant here. `leaprun` is a command runner; any time a command like
`leaprun ACTION` is run, the corresponding `Command` under the same-named
`ACTION` in `/usr/lib/privleap/conf.d/sdwdate.conf` will be run using the
`bash` shell with the privileges of the specified `TargetUser` (or `root` if no
`TargetUser` is specified). Only code running under a user or group listed
under `AuthorizedUsers` or `AuthorizedGroups` for an action will be allowed to
run that action. The source code of `privleap` is intentionally not provided
and `privleap`'s exact behavior is out of scope.

Reviewers will also see references to "qubes". Qubes OS is a desktop hypervisor
that runs typical Linux applications in virtual machines (an individual VM may
be referred to as a "qube"). Some VMs are "templates", which have no Internet
access, while others are "AppVMs", which typically have Internet access and
which inherit most of their root filesystem from a template. This split, and
some other behaviors of the Qubes hypervisor, requires special-casing in some
areas of sdwdate's code.

Other references to external projects in the code are expected to be well-known
and without need for explanation.

All non-documentation files that are part of sdwdate are in-scope for review,
but special attention should be given to any code that accesses the network or
handles data fetched from a network source. Especially important is
`/usr/bin/url_to_unixtime`. Files such as AppArmor configuration, systemd
configuration, etc., are less important, but may still be useful when
determining the impact of a vulnerability.

## Environment

sdwdate will always run on a Debian 13 machine, with the default
Debian-provided versions of python3 (that is, Python 3.13) and any other
dependencies present in the official Debian repositories. Misbehavior that is
only present when using dependencies newer than those available in Debian 13
may be flagged as vulnerabilities, but their severity will always be low or at
worst medium. Misbehavior that is only present when using older dependencies is
explicitly out of scope and should not be reported.

## Reviewing and exercising code

Due to sdwdate's heavy focus on retrieving data from the network over Tor
specifically, it is not possible to meaningfully run sdwdate in an offline test
sandbox without simulating a Tor network or part of a Tor network within the
sandbox. Reviewers may choose to do this if they wish, but are not required or
encouraged to, due to the time and resource consumption this would entail.
Instead, reviewers are encouraged to write Python scripts using Python's
`unittest.mock` library to prepare functions within sdwdate's code for being
run standalone, then analyze their behavior under those mocks. Mock behavior
should not stray outside of what may be expected in real-world operation.
Similar techniques may be used to analyze the behavior of Bash scripts in the
codebase if those scripts cannot be meaningfully run standalone.

If all else fails, relying solely on static analysis / "reading through the
code and working out the logic" is permissible. The severity of vulnerabilities
found using this method is unchanged, but vulnerability reports should mention
if this method was used to help maintainers prioritize them accordingly.
