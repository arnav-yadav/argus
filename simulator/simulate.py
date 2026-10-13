"""Heartbeat simulator for Argus demos.

Registers a small fleet of fake services, each with its own reliability profile, and
sends heartbeats for them forever. Uses only the standard library so the image stays
tiny and has nothing to patch.
"""

import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

API = os.environ.get("ARGUS_API", "http://localhost:8000").rstrip("/")


@dataclass
class Profile:
    name: str
    slug: str
    interval_s: int
    slo_target: float
    fail_rate: float = 0.0  # chance a beat reports "fail"
    degraded_rate: float = 0.0  # chance a beat reports "degraded" with high latency
    silent_every_s: int = 0  # go quiet periodically to simulate an outage...
    silent_for_s: int = 0  # ...for this long
    service_id: int | None = field(default=None, init=False)
    token: str | None = field(default=None, init=False)
    next_beat: float = field(default=0.0, init=False)


FLEET = [
    Profile("Checkout API", "checkout-api", 10, 99.9, fail_rate=0.001),
    Profile("Search", "search", 10, 99.5),
    Profile("Payments Gateway", "payments-gateway", 10, 99.9, fail_rate=0.02),
    Profile("Recommendations", "recommendations", 15, 99.0, degraded_rate=0.3),
    Profile("Legacy Billing", "legacy-billing", 10, 99.5, silent_every_s=600, silent_for_s=90),
]


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{API}{path}", data=data, method=method)  # noqa: S310
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("X-Argus-Token", token)
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - fixed base URL
        raw = response.read()
        return json.loads(raw) if raw else None


def enrol(profile: Profile) -> None:
    """Register the service, or take over an existing one by rotating its token."""
    existing = call("GET", f"/api/services?slug={profile.slug}")
    if existing:
        profile.service_id = existing[0]["id"]
        profile.token = call("POST", f"/api/services/{profile.service_id}/rotate-token")[
            "ingest_token"
        ]
        print(f"took over {profile.slug} (id {profile.service_id})", flush=True)
        return
    created = call(
        "POST",
        "/api/services",
        {
            "name": profile.name,
            "slug": profile.slug,
            "heartbeat_interval_s": profile.interval_s,
            "slo_target": profile.slo_target,
        },
    )
    profile.service_id, profile.token = created["id"], created["ingest_token"]
    print(f"registered {profile.slug} (id {profile.service_id})", flush=True)


def is_silent(profile: Profile, now: float) -> bool:
    return bool(profile.silent_every_s) and (now % profile.silent_every_s) < profile.silent_for_s


def beat(profile: Profile) -> None:
    roll = random.random()  # noqa: S311 - not cryptographic, just demo noise
    if roll < profile.fail_rate:
        status, latency = "fail", random.randint(800, 3000)  # noqa: S311
    elif roll < profile.fail_rate + profile.degraded_rate:
        status, latency = "degraded", random.randint(600, 1500)  # noqa: S311
    else:
        status, latency = "ok", random.randint(15, 120)  # noqa: S311
    call(
        "POST",
        f"/api/services/{profile.service_id}/heartbeat",
        {"status": status, "latency_ms": latency},
        profile.token,
    )


def main() -> None:
    print(f"simulating {len(FLEET)} services against {API}", flush=True)
    while True:
        try:
            for profile in FLEET:
                enrol(profile)
            break
        except (urllib.error.URLError, OSError) as error:
            print(f"API not ready ({error}); retrying in 3s", flush=True)
            time.sleep(3)

    while True:
        now = time.time()
        for profile in FLEET:
            if now < profile.next_beat:
                continue
            # Beat a little early with jitter: the loop only wakes once a second, so scheduling at
            # 60-80% of the interval guarantees every slot gets a beat while healthy.
            profile.next_beat = now + profile.interval_s * random.uniform(0.6, 0.8)  # noqa: S311
            if is_silent(profile, now):
                continue
            try:
                beat(profile)
            except urllib.error.HTTPError as error:
                if error.code in (401, 404):  # token rotated elsewhere or service deleted
                    print(f"{profile.slug}: {error.code}, re-enrolling", flush=True)
                    try:
                        enrol(profile)
                    except (urllib.error.URLError, OSError) as retry_error:
                        print(f"{profile.slug}: re-enrol failed ({retry_error})", flush=True)
            except (urllib.error.URLError, OSError) as error:
                print(f"{profile.slug}: {error}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
