import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import { UPDATE_HANDOFF_FILE } from "./update.env";

/**
 * Playwright `globalTeardown` for the `update` project (private-household-
 * deployment ticket 04b).
 *
 * `e2e/update-server.mjs` starts the deployment with a BACKGROUNDED
 * `deploy/control.sh start`, which detaches it into its own session. Playwright
 * killing the `webServer` process does not reach a detached session, so the
 * deployment is stopped here — in Playwright's own process, which always runs
 * before the suite exits — reading the layout the harness recorded in the
 * handoff file.
 */
export default function globalTeardown(): void {
  if (!existsSync(UPDATE_HANDOFF_FILE)) return;
  try {
    const { repoRoot, deployEnv } = JSON.parse(
      readFileSync(UPDATE_HANDOFF_FILE, "utf8"),
    ) as { repoRoot: string; deployEnv: Record<string, string> };
    execFileSync(
      "bash",
      [path.join(repoRoot, "deploy", "control.sh"), "stop"],
      {
        env: deployEnv,
        stdio: "inherit",
      },
    );
  } catch {
    // best effort — the harness's own signal handler and next-run sweep also cover this
  } finally {
    rmSync(path.dirname(UPDATE_HANDOFF_FILE), { recursive: true, force: true });
  }
}
