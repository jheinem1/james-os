/*
 * Vencord, a Discord client mod
 * Copyright (c) 2026 Vendicated and contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import { IpcMainInvokeEvent } from "electron";
import { chmodSync, existsSync, rmSync } from "fs";
import { createServer, Server } from "net";
import { join } from "path";

const socketPath = join(process.env.XDG_RUNTIME_DIR || "/tmp", "vencord-kde-idle-sync.sock");

let server: Server | null = null;

function sendState(event: IpcMainInvokeEvent, state: "active" | "inactive") {
    void event.sender.executeJavaScript(
        `Vencord?.Plugins?.plugins?.KdeIdleSync?.handleExternalState?.(${JSON.stringify(state)})`
    );
}

function attachServerListener(event: IpcMainInvokeEvent) {
    if (!server) {
        return;
    }

    server.removeAllListeners("connection");

    server.on("connection", socket => {
        let buffer = "";

        socket.setEncoding("utf8");
        socket.on("data", chunk => {
            buffer += chunk;

            while (buffer.includes("\n")) {
                const newline = buffer.indexOf("\n");
                const command = buffer.slice(0, newline).trim().toLowerCase();
                buffer = buffer.slice(newline + 1);

                if (command === "active" || command === "inactive") {
                    sendState(event, command);
                }
            }
        });

        socket.on("error", () => void 0);
    });
}

export function startServer(event: IpcMainInvokeEvent) {
    if (!server) {
        if (existsSync(socketPath)) {
            rmSync(socketPath, { force: true });
        }

        server = createServer();
        server.listen(socketPath, () => chmodSync(socketPath, 0o600));
    }

    attachServerListener(event);
    return socketPath;
}

export function stopServer() {
    if (!server) {
        if (existsSync(socketPath)) {
            rmSync(socketPath, { force: true });
        }

        return;
    }

    const currentServer = server;
    server = null;

    currentServer.close(() => {
        if (existsSync(socketPath)) {
            rmSync(socketPath, { force: true });
        }
    });
}
