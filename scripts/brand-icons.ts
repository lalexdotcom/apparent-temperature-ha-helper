/**
 * Render the integration's brand icon.
 *
 *   pnpm exec tsx scripts/brand-icons.ts            icon.png + icon@2x.png
 *   pnpm exec tsx scripts/brand-icons.ts --preview  contact sheets of variants
 *
 * HACS's `brands` validator accepts a local asset at
 * custom_components/<domain>/brand/icon.png instead of an entry in the Home
 * Assistant brands repository, which is the only one of the two that does not
 * depend on anyone else. See custom_components/hacs/validate/brands.py.
 *
 * The drawing is Material Design Icons' `thermometer-lines`, split into its
 * three groups of subpaths so each can take its own colour: the four bars on
 * the left, the four on the right, and the thermometer between them. The
 * mercury column is a hole in that last subpath and stays one, so it takes the
 * colour of whatever the icon is displayed on — a backdrop, or the page.
 */
import { mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const LEFT_BARS =
	"M7 3V5H3V3H7M7 7V9H3V7H7M7 11V12.1L6.25 13H3V11H7M3 15H5.29C5.1 15.63 5 16.31 5 17H3V15";
const RIGHT_BARS =
	"M17 3H21V5H17V3M17 7H21V9H17V7M17 11H21V13H17.75L17 12.1V11M21 15V17H19C19 16.31 18.9 15.63 18.71 15H21";
const STEM =
	"M15 13V5C15 3.34 13.66 2 12 2S9 3.34 9 5V13C6.79 14.66 6.34 17.79 8 20S12.79 22.66 15 21 17.66 16.21 16 14C15.72 13.62 15.38 13.28 15 13";

// Home Assistant's palette, from the frontend's
// src/resources/theme/color/{color,core}.globals.ts.
const HA_BLUE = "#2196f3";
const HA_RED = "#f44336";
const HA_AMBER = "#ffc107";
const HA_NEUTRAL_05 = "#141414";
const HA_NEUTRAL_95 = "#f3f3f3";

/**
 * The mercury column, whose two bottom anchors sit at `tubeBottom`. MDI draws
 * it ending at 8, less than halfway down a stem that runs to 13; lowering it
 * lengthens the hole without touching its width or its rounded top.
 */
function mercuryHole(tubeBottom: number): string {
	return `M12 4C12.55 4 13 4.45 13 5V${tubeBottom}H11V5C11 4.45 11.45 4 12 4Z`;
}

type Icon = { body: string; cold: string; hot: string; tubeBottom: number };

const ICON: Icon = { body: HA_AMBER, cold: HA_BLUE, hot: HA_RED, tubeBottom: 9 };

/** The three paths, in a 24×24 space, ready to be placed in an outer SVG. */
function paths({ body, cold, hot, tubeBottom }: Icon): string {
	return `<path d="${LEFT_BARS}" fill="${cold}"/>
	<path d="${RIGHT_BARS}" fill="${hot}"/>
	<path d="${STEM}${mercuryHole(tubeBottom)}" fill="${body}"/>`;
}

/**
 * A backdrop behind the icon. Every length is a percentage of the tile's side:
 * `radius` 50 is a circle and 0 a square, `share` is how much of the side the
 * drawing itself takes, `border` is the stroke, drawn fully inside the edge.
 */
type Backdrop = { fill: string; stroke: string; radius: number; share: number; border: number };

type Box = { x: number; y: number; width: number; height: number };

/**
 * `share` counts the ink, not the icon's box. MDI leaves margin inside its
 * 24×24 viewBox — the drawing spans 18 units across and 20 down — so scaling
 * the box makes a nominal 72% read as 54% wide, which is what makes the icon
 * look lost on its backdrop. Measuring the bounding box in the browser and
 * fitting that instead keeps the number honest, and keeps it honest if the
 * drawing ever changes.
 */
function badgeSvg(icon: Icon, backdrop: Backdrop, ink: Box, size: number): string {
	const { fill, stroke, radius, share, border } = backdrop;
	const scale = share / Math.max(ink.width, ink.height);
	const x = (100 - ink.width * scale) / 2 - ink.x * scale;
	const y = (100 - ink.height * scale) / 2 - ink.y * scale;
	return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="${size}" height="${size}">
	<rect x="${border / 2}" y="${border / 2}" width="${100 - border}" height="${100 - border}"
		rx="${radius}" ry="${radius}" fill="${fill}" stroke="${stroke}" stroke-width="${border}"/>
	<g transform="translate(${x} ${y}) scale(${scale})">${paths(icon)}</g>
</svg>`;
}

/** The drawing's real bounding box in its 24×24 space, measured by Chromium. */
async function measureInk(
	browser: Awaited<ReturnType<typeof chromium.launch>>,
	icon: Icon,
): Promise<Box> {
	const page = await browser.newPage();
	await page.setContent(
		`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="240" height="240">
		<g id="ink">${paths(icon)}</g></svg>`,
	);
	const box = await page.evaluate(() => {
		const { x, y, width, height } = (
			document.getElementById("ink") as unknown as SVGGraphicsElement
		).getBBox();
		return { x, y, width, height };
	});
	await page.close();
	return box;
}

// Chosen from the previous sheets: a squircle on Home Assistant's darkest
// neutral, outlined in its lightest one, the drawing taking 68% of the side.
const BADGE: Backdrop = {
	fill: HA_NEUTRAL_05,
	stroke: HA_NEUTRAL_95,
	radius: 34,
	share: 68,
	border: 3,
};

const SHARES = [60, 68, 76, 84];

function cell(art: string, caption: string, ground: string, ink: string): string {
	return `<div style="background:${ground};color:${ink};padding:14px 8px;text-align:center;
		border-radius:10px;width:132px">${art}
		<div style="font:12px system-ui;margin-top:10px">${caption}</div></div>`;
}

function sheet(rows: string[]): string {
	return `<body style="margin:0;padding:20px;background:#9e9e9e;display:flex;
		flex-direction:column;gap:12px;width:max-content">${rows.join("")}</body>`;
}

function row(cells: string[]): string {
	return `<div style="display:flex;gap:12px">${cells.join("")}</div>`;
}

async function shoot(
	browser: Awaited<ReturnType<typeof chromium.launch>>,
	html: string,
	path: string,
): Promise<void> {
	const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
	await page.setContent(html);
	await page.screenshot({ path, fullPage: true });
	await page.close();
}

async function main(): Promise<void> {
	const browser = await chromium.launch();

	try {
		const ink = await measureInk(browser, ICON);
		if (process.argv.includes("--preview")) {
			const out = join(repoRoot, ".brand-preview");
			rmSync(out, { recursive: true, force: true });
			mkdirSync(out, { recursive: true });

			// Both grounds: the light border is what disappears on a light page,
			// and the dark fill is what disappears on a dark one.
			const grounds: [string, string][] = [
				["#ffffff", "#212121"],
				["#1c1c1c", "#e8eaed"],
			];

			const shareRow = (ground: string, pen: string) =>
				row(
					SHARES.map((share) =>
						cell(badgeSvg(ICON, { ...BADGE, share }, ink, 104), `${share}%`, ground, pen),
					),
				);
			await shoot(
				browser,
				sheet(grounds.map(([ground, pen]) => shareRow(ground, pen))),
				join(out, "share.png"),
			);

			console.log("Wrote share.png to .brand-preview/");
		} else {
			const out = join(repoRoot, "custom_components", "apparent_temperature", "brand");
			mkdirSync(out, { recursive: true });
			for (const [size, name] of [
				[256, "icon.png"],
				[512, "icon@2x.png"],
			] as const) {
				const page = await browser.newPage({ viewport: { width: size, height: size } });
				// The margin matters: Chromium wraps a bare SVG in a body that has
				// one, which pushed the badge down and to the right and let the
				// viewport-sized screenshot crop its border off two sides.
				await page.setContent(`<body style="margin:0">${badgeSvg(ICON, BADGE, ink, size)}</body>`);
				await page.screenshot({ path: join(out, name), omitBackground: true });
				await page.close();
			}
			console.log(`Wrote icon.png and icon@2x.png to ${out}`);
		}
	} finally {
		await browser.close();
	}
}

// package.json declares no `"type": "module"`, so tsx compiles this to CJS,
// where a top-level await is a syntax error.
main().catch((error: unknown) => {
	console.error(error);
	process.exit(1);
});
