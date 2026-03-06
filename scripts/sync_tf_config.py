#!/usr/bin/env python3
"""
Reads Terraform outputs and updates .chalice/config.json production stage.
Run after `terraform apply` and before `chalice deploy`.
"""
import json
import subprocess
import sys
import os

INFRA_DIR = os.path.join(os.path.dirname(__file__), "..", "terraform")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", ".chalice", "config.json")


def tf_output(name):
    result = subprocess.run(
        ["terraform", f"-chdir={INFRA_DIR}", "output", "-raw", name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error reading terraform output '{name}': {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()


def main():
    bucket = tf_output("bucket_name")
    role_arn = tf_output("lambda_exec_role_arn")

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    prod = config["stages"]["production"]
    prod["manage_iam_role"] = False
    prod["iam_role_arn"] = role_arn

    env = prod.setdefault("environment_variables", {})
    env["APP_ENV"] = "production"
    env["BOT_DATA_BUCKET"] = bucket

    # autogen_policy is irrelevant when manage_iam_role is False
    prod.pop("autogen_policy", None)

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(f"Updated {CONFIG_PATH}:")
    print(f"  iam_role_arn:      {role_arn}")
    print(f"  BOT_DATA_BUCKET:   {bucket}")


if __name__ == "__main__":
    main()