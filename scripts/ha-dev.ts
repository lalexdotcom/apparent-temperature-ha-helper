/**
 * Launch a throwaway Home Assistant instance from the official image, with
 * this repository's custom component mounted into it.
 *
 *   pnpm run ha             reuse .ha-dev/, keeping whatever was configured
 *   pnpm run ha -- --reset  start from an empty config directory
 *
 * The config directory is deliberately reused between runs: helpers created
 * through the UI, and the onboarding account, survive a restart. Only --reset
 * throws that away.
 *
 * HA_VERSION overrides the image tag (default: stable).
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const configDir = join(repoRoot, ".ha-dev");
const componentSource = join(repoRoot, "custom_components", "apparent_temperature");
const image = `ghcr.io/home-assistant/home-assistant:${process.env.HA_VERSION ?? "stable"}`;

// Seed sensors, deliberately in mixed units, so the helper has something to
// select and the unit conversion is visible rather than theoretical.
const CONFIGURATION = `default_config:

logger:
  default: info
  logs:
    custom_components.apparent_temperature: debug

template:
  - sensor:
      - name: Dev temperature celsius
        unique_id: dev_temperature_celsius
        state: "18.4"
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
      - name: Dev temperature fahrenheit
        unique_id: dev_temperature_fahrenheit
        state: "68.0"
        unit_of_measurement: "°F"
        device_class: temperature
        state_class: measurement
      - name: Dev humidity
        unique_id: dev_humidity
        state: "62"
        unit_of_measurement: "%"
        device_class: humidity
        state_class: measurement
      - name: Dev wind kmh
        unique_id: dev_wind_kmh
        state: "24"
        unit_of_measurement: "km/h"
        device_class: wind_speed
        state_class: measurement
      - name: Dev wind beaufort
        unique_id: dev_wind_beaufort
        state: "5"
        unit_of_measurement: "Beaufort"
        device_class: wind_speed
        state_class: measurement
`;

if (spawnSync("docker", ["info"], { stdio: "ignore" }).status !== 0) {
	console.error(
		"Docker is not reachable. The devcontainer's docker-in-docker feature provides it.",
	);
	process.exit(1);
}
if (!existsSync(componentSource)) {
	console.error(`No component at ${componentSource}.`);
	process.exit(1);
}

if (process.argv.includes("--reset") && existsSync(configDir)) {
	rmSync(configDir, { recursive: true, force: true });
	console.log("Reset .ha-dev/");
}

mkdirSync(configDir, { recursive: true });
const configurationYaml = join(configDir, "configuration.yaml");
if (!existsSync(configurationYaml)) {
	writeFileSync(configurationYaml, CONFIGURATION);
}

console.log(`Home Assistant (${image}) starting on http://localhost:8123`);
console.log("Settings > Devices & services > Helpers > Create helper > Apparent temperature");
console.log("Ctrl-C stops it; --rm means the container leaves nothing behind.");

// The component is a second, read-only bind nested inside /config: Home
// Assistant never writes there, and mounting it separately keeps the source of
// truth in the repository rather than a copy that silently goes stale.
const child = spawn(
	"docker",
	[
		"run",
		"--rm",
		"-it",
		"--name",
		"apparent-temperature-ha-dev",
		"-p",
		"8123:8123",
		"-e",
		`TZ=${process.env.TZ ?? "Europe/Paris"}`,
		"-v",
		`${configDir}:/config`,
		"-v",
		`${componentSource}:/config/custom_components/apparent_temperature:ro`,
		image,
	],
	{ stdio: "inherit" },
);
child.on("exit", (code) => process.exit(code ?? 0));
