#!/usr/bin/env node
import { renameSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const discordResources = "/usr/share/discord/resources";
const appAsar = join(discordResources, "app.asar");
const originalAppAsar = join(discordResources, "_app.asar");
const tempAppAsar = join(discordResources, "app.asar.tmp");
const vencordPatcher = "/usr/share/vencord/patcher.js";

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

try {
    renameSync(appAsar, originalAppAsar);

    const indexJs = `require(${JSON.stringify(vencordPatcher)});`;
    writeFileSync(tempAppAsar, buildAsar({
        "index.js": indexJs,
        "package.json": packageJson
    }));
    renameSync(tempAppAsar, appAsar);
} catch (error) {
    rmSync(tempAppAsar, { force: true });
    throw new Error(`Failed to patch ${appAsar}: ${error.message}`);
}

console.log(`Patched ${appAsar} to load ${vencordPatcher}`);
console.log(`Original Discord app archive moved to ${originalAppAsar}`);
