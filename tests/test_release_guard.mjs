import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { verifySource, verifyRelease } from "../scripts/release-guard.mjs";
import { fileURLToPath } from "node:url";

test("publication refuses changed versions before consulting Git", () => {
  assert.throws(() => verifyRelease({}, { env: { EXPECTED_RELEASE_VERSION: "1.2.3" },
    nextRelease: { version: "1.2.4" } }), /version changed/);
});

test("publication binds checkout, dispatch, repository, branch and current remote main", () => {
  const temporary = mkdtempSync(path.join(tmpdir(), "shared-release-guard-"));
  const env = { PATH: process.env.PATH, HOME: temporary, GIT_CONFIG_NOSYSTEM: "1",
    GIT_CONFIG_GLOBAL: path.join(temporary, "empty-config"),
    GITHUB_REF: "refs/heads/main", GITHUB_REPOSITORY: "please-behave/cli",
    PLEASE_RELEASE_REPOSITORY: "please-behave/cli", EXPECTED_RELEASE_VERSION: "1.2.3" };
  const git = (...args) => execFileSync("git", args, { cwd: temporary, env, encoding: "utf8", stdio: "pipe" }).trim();
  try {
    git("init", "--bare", "--initial-branch=main", "remote.git");
    git("init", "--initial-branch=main");
    git("config", "user.name", "Release Fixture");
    git("config", "user.email", "fixture@example.invalid");
    git("remote", "add", "origin", path.join(temporary, "remote.git"));
    git("commit", "--allow-empty", "-m", "feat: create fixture");
    git("push", "origin", "main");
    env.GITHUB_SHA = git("rev-parse", "HEAD");
    const context = { cwd: temporary, env, nextRelease: { version: "1.2.3" } };
    verifyRelease({}, context);
    execFileSync(process.execPath, [fileURLToPath(new URL("../scripts/release-guard.mjs", import.meta.url)), "--source"],
      { cwd: temporary, env, stdio: "pipe" });
    for (const field of ["GITHUB_SHA", "GITHUB_REF", "GITHUB_REPOSITORY", "PLEASE_RELEASE_REPOSITORY"]) {
      assert.throws(() => verifySource({ ...env, [field]: "foreign" }, temporary));
    }
    git("commit", "--allow-empty", "-m", "fix: move main");
    assert.throws(() => verifyRelease({}, context), /main changed/);
    git("push", "origin", "main");
    git("checkout", "--detach", env.GITHUB_SHA);
    assert.throws(() => verifyRelease({}, context), /main changed/);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});
