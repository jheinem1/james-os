#!/usr/bin/env node
import {
    existsSync,
    readFileSync,
    renameSync,
    rmSync,
    statSync,
    writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";

const discordResourcesArg = process.argv[2];
if (!discordResourcesArg) {
    throw new Error("Usage: patch-discord-vencord-asar.mjs /path/to/discord/resources [vencord-patcher]");
}

const discordResources = resolve(discordResourcesArg);
const appAsar = join(discordResources, "app.asar");
const originalAppAsar = join(discordResources, "_app.asar");
const tempAppAsar = join(discordResources, ".app.asar.vencord.tmp");
const vencordPatcher = resolve(process.argv[3] || "/usr/share/vencord/patcher.js");
const vencordDist = dirname(vencordPatcher);

const packageJson = `{
    "name": "discord",
    "main": "index.js"
}`;

function asarEntry(size, offset) {
    return { size, offset: String(offset) };
}

function buildAsar(files) {
    const headerFiles = {};
    const chunks = [];
    let offset = 0;

    for (const [name, content] of Object.entries(files)) {
        const bytes = Buffer.from(content);
        headerFiles[name] = asarEntry(bytes.length, offset);
        chunks.push(bytes);
        offset += bytes.length;
    }

    const header = JSON.stringify({ files: headerFiles });
    const headerBytes = Buffer.from(header);
    const dataSize = 4;
    const alignedSize = (headerBytes.length + dataSize - 1) & ~(dataSize - 1);
    const headerSize = alignedSize + 8;
    const headerObjectSize = alignedSize + dataSize;
    const padding = Buffer.from("0".repeat(alignedSize - headerBytes.length));

    const sizeHeader = Buffer.alloc(16);
    sizeHeader.writeInt32LE(dataSize, 0);
    sizeHeader.writeInt32LE(headerSize, 4);
    sizeHeader.writeInt32LE(headerObjectSize, 8);
    sizeHeader.writeInt32LE(headerBytes.length, 12);

    return Buffer.concat([sizeHeader, headerBytes, padding, ...chunks]);
}

for (const requiredPath of [
    appAsar,
    vencordPatcher,
    join(vencordDist, "preload.js"),
    join(vencordDist, "renderer.js"),
    join(vencordDist, "renderer.css"),
]) {
    if (!existsSync(requiredPath)) {
        throw new Error(`Required file is missing: ${requiredPath}`);
    }
}

function isExpectedLoader(path) {
    if (!existsSync(path) || statSync(path).size > 1024 * 1024) {
        return false;
    }

    return readFileSync(path).includes(Buffer.from(vencordPatcher));
}

if (isExpectedLoader(appAsar) && existsSync(originalAppAsar)) {
    process.exit(0);
}

const indexJs = `require(${JSON.stringify(vencordPatcher)});`;
const loader = buildAsar({
    "index.js": indexJs,
    "package.json": packageJson
});

rmSync(tempAppAsar, { force: true });
writeFileSync(tempAppAsar, loader, { mode: 0o644 });

let movedOriginal = false;
try {
    if (!existsSync(originalAppAsar)) {
        renameSync(appAsar, originalAppAsar);
        movedOriginal = true;
    }

    renameSync(tempAppAsar, appAsar);
} catch (error) {
    rmSync(tempAppAsar, { force: true });
    if (movedOriginal && !existsSync(appAsar) && existsSync(originalAppAsar)) {
        renameSync(originalAppAsar, appAsar);
    }
    throw new Error(`Failed to patch ${appAsar}: ${error.message}`);
}

console.log(`Patched ${appAsar} to load ${vencordPatcher}`);
console.log(`Original Discord app archive is at ${originalAppAsar}`);
