"""Task handlers. Add your own with @task("name")."""
import random
import time

TASKS = {}


def task(name):
    def register(fn):
        TASKS[name] = fn
        return fn
    return register


@task("echo")
def echo(payload):
    print(f"echo: {payload}", flush=True)


@task("sleep")
def sleep(payload):
    time.sleep(float(payload.get("seconds", 1)))


@task("fail")
def always_fail(payload):
    raise RuntimeError("this task always fails")


@task("flaky")
def flaky(payload):
    if random.random() < float(payload.get("fail_rate", 0.5)):
        raise RuntimeError("random failure")
