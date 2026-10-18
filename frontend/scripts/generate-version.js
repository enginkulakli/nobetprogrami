const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const repoRoot = path.resolve(__dirname, "../..");
let commit = "local";
try {
  commit = execFileSync("git", ["-C", repoRoot, "rev-parse", "--short=7", "HEAD"], { encoding: "utf8" }).trim();
} catch (_) {
  // Local builds outside a Git checkout still get a timestamped version.
}

const now = new Date();
const pad = (value) => String(value).padStart(2, "0");
const date = `${now.getUTCFullYear()}.${pad(now.getUTCMonth() + 1)}.${pad(now.getUTCDate())}`;
const version = `${date}-${commit}`;
const buildTime = `${date.replaceAll(".", "-")} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}`;
const output = path.resolve(__dirname, "../src/generatedVersion.js");

fs.writeFileSync(
  output,
  `export const APP_VERSION = ${JSON.stringify(version)};\nexport const APP_BUILD_TIME = ${JSON.stringify(buildTime)};\n`,
  "utf8"
);

console.log(`Building site version ${version} (${buildTime} UTC)`);
