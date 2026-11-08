/*
 * Vencord, a Discord client mod
 * Copyright (c) 2026 Vendicated and contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import { IpcMainInvokeEvent, WebContents } from "electron";
import { chmodSync, existsSync, rmSync, statSync } from "fs";
import { createServer, Server, Socket } from "net";
import { basename, isAbsolute, join } from "path";

const socketPath = join(process.env.XDG_RUNTIME_DIR || "/tmp", "vencord-codex-window-control.sock");
const maxRequestBytes = 64 * 1024;
const maxFileBytes = 100 * 1024 * 1024;

type JsonObject = Record<string, unknown>;

interface Request extends JsonObject {
    action: string;
    allowMutation?: boolean;
    timeoutMs?: number;
}

let server: Server | null = null;

function boundedTimeout(value: unknown, fallback = 5_000) {
    return Math.min(Math.max(Number(value) || fallback, 100), 15_000);
}

function writeResponse(socket: Socket, response: JsonObject) {
    if (!socket.destroyed) {
        socket.end(`${JSON.stringify(response)}\n`);
    }
}

async function inspect(webContents: WebContents) {
    return await webContents.executeJavaScript(`(() => {
        const visible = element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0 && rect.height > 0
                && style.visibility !== "hidden" && style.display !== "none";
        };
        const name = element => (
            element.getAttribute("aria-label")
            || element.getAttribute("title")
            || element.getAttribute("placeholder")
            || element.innerText
            || element.value
            || ""
        ).trim().replace(/\\s+/g, " ").slice(0, 180);
        const selector = [
            "button", "a[href]", "[role=button]", "[role=link]",
            "input", "textarea", "[contenteditable=true]"
        ].join(",");
        return {
            title: document.title,
            url: location.href,
            recentAttachments: Array.from(document.querySelectorAll(
                '[data-list-item-id^="chat-messages"] a[href],'
                + '[data-list-item-id^="chat-messages"] img[src],'
                + '[id^="chat-messages"] a[href],'
                + '[id^="chat-messages"] img[src]'
            )).map(element => element.getAttribute("href") || element.getAttribute("src"))
                .filter(url => url?.includes("/attachments/"))
                .slice(-20)
                .map(url => {
                    try {
                        return decodeURIComponent(new URL(url).pathname.split("/").pop() || "");
                    } catch {
                        return "";
                    }
                })
                .filter(Boolean),
            interactives: Array.from(document.querySelectorAll(selector))
                .filter(visible)
                .slice(0, 250)
                .map(element => ({
                    role: element.getAttribute("role") || element.tagName.toLowerCase(),
                    name: name(element),
                    disabled: element.matches(":disabled,[aria-disabled=true]")
                }))
        };
    })()`, true);
}

async function waitUntil(check: () => Promise<boolean>, timeoutMs: number) {
    const deadline = Date.now() + timeoutMs;
    do {
        if (await check()) {
            return true;
        }
        await new Promise(resolve => setTimeout(resolve, 100));
    } while (Date.now() < deadline);
    return false;
}

async function waitForText(webContents: WebContents, text: string, timeoutMs: number) {
    return await waitUntil(
        async () => await webContents.executeJavaScript(
            `document.body?.innerText?.includes(${JSON.stringify(text)}) === true`,
            true
        ),
        timeoutMs
    );
}

async function waitForTitle(webContents: WebContents, pattern: string, timeoutMs: number) {
    const regex = new RegExp(pattern);
    return await waitUntil(async () => regex.test(await webContents.getTitle()), timeoutMs);
}

async function verifyPostcondition(webContents: WebContents, request: Request) {
    if (typeof request.expectText === "string") {
        const verified = await waitForText(
            webContents,
            request.expectText,
            boundedTimeout(request.timeoutMs)
        );
        return { kind: "text", expected: request.expectText, verified };
    }

    if (typeof request.expectTitleRegex === "string") {
        const verified = await waitForTitle(
            webContents,
            request.expectTitleRegex,
            boundedTimeout(request.timeoutMs)
        );
        return { kind: "title", expected: request.expectTitleRegex, verified };
    }

    return null;
}

async function click(webContents: WebContents, request: Request) {
    if (request.allowMutation !== true) {
        throw new Error("click requires allowMutation=true");
    }
    if (typeof request.name !== "string" || request.name.length === 0 || request.name.length > 180) {
        throw new Error("click requires a non-empty name of at most 180 characters");
    }

    const exact = request.exact !== false;
    const result = await webContents.executeJavaScript(`(() => {
        const requested = ${JSON.stringify(request.name)};
        const exact = ${JSON.stringify(exact)};
        const visible = element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0 && rect.height > 0
                && style.visibility !== "hidden" && style.display !== "none";
        };
        const name = element => (
            element.getAttribute("aria-label")
            || element.getAttribute("title")
            || element.innerText
            || element.value
            || ""
        ).trim().replace(/\\s+/g, " ").slice(0, 180);
        const elements = Array.from(document.querySelectorAll(
            "button,a[href],[role=button],[role=link]"
        )).filter(element => visible(element) && !element.matches(":disabled,[aria-disabled=true]"));
        const matches = elements.filter(element => {
            const candidate = name(element);
            return exact ? candidate === requested : candidate.includes(requested);
        });
        if (matches.length !== 1) {
            return {
                injected: false,
                reason: matches.length === 0 ? "not-found" : "ambiguous",
                matches: matches.slice(0, 20).map(name)
            };
        }
        matches[0].click();
        return { injected: true, target: name(matches[0]) };
    })()`, true);

    if (!result.injected) {
        return { ok: false, status: "not-injected", ...result };
    }

    const postcondition = await verifyPostcondition(webContents, request);
    if (!postcondition) {
        return { ok: true, status: "mutation-injected", ...result };
    }

    return {
        ok: postcondition.verified,
        status: postcondition.verified ? "postcondition-verified" : "injected-unverified",
        postcondition,
        ...result
    };
}

async function navigateToNamedChannel(webContents: WebContents, request: Request) {
    if (request.allowMutation !== true) {
        throw new Error("navigateToNamedChannel requires allowMutation=true");
    }
    if (typeof request.guildName !== "string" || request.guildName.length === 0 || request.guildName.length > 100) {
        throw new Error("navigateToNamedChannel requires guildName of at most 100 characters");
    }
    if (typeof request.channelName !== "string" || request.channelName.length === 0 || request.channelName.length > 100) {
        throw new Error("navigateToNamedChannel requires channelName of at most 100 characters");
    }

    const result = await webContents.executeJavaScript(`(() => {
        const requestedGuild = ${JSON.stringify(request.guildName)};
        const requestedChannel = ${JSON.stringify(request.channelName)};
        const normalize = value => String(value || "").trim().toLocaleLowerCase();
        const common = globalThis.Vencord?.Webpack?.Common;
        if (!common?.GuildStore?.getGuilds || !common?.GuildChannelStore?.getChannels
            || !common?.NavigationRouter?.transitionTo) {
            return { transitioned: false, reason: "discord-stores-unavailable" };
        }

        const guildMatches = Object.values(common.GuildStore.getGuilds())
            .filter(guild => normalize(guild.name) === normalize(requestedGuild));
        if (guildMatches.length !== 1) {
            return {
                transitioned: false,
                reason: guildMatches.length === 0 ? "guild-not-found" : "guild-ambiguous",
                guildMatches: guildMatches.map(guild => ({ id: guild.id, name: guild.name }))
            };
        }

        const guild = guildMatches[0];
        const groups = common.GuildChannelStore.getChannels(guild.id);
        const entries = Array.isArray(groups?.SELECTABLE) ? groups.SELECTABLE : [];
        const channelMatches = entries
            .map(entry => entry.channel)
            .filter(channel => normalize(channel?.name) === normalize(requestedChannel));
        if (channelMatches.length !== 1) {
            return {
                transitioned: false,
                reason: channelMatches.length === 0 ? "channel-not-found" : "channel-ambiguous",
                guild: { id: guild.id, name: guild.name },
                channelMatches: channelMatches.map(channel => ({ id: channel.id, name: channel.name }))
            };
        }

        const channel = channelMatches[0];
        common.NavigationRouter.transitionTo("/channels/" + guild.id + "/" + channel.id);
        return {
            transitioned: true,
            guild: { id: guild.id, name: guild.name },
            channel: { id: channel.id, name: channel.name }
        };
    })()`, true);

    if (!result.transitioned) {
        return { ok: false, status: "not-injected", ...result };
    }

    const verified = await waitUntil(
        async () => await webContents.executeJavaScript(
            `location.pathname === ${JSON.stringify(`/channels/${result.guild.id}/${result.channel.id}`)}`,
            true
        ),
        boundedTimeout(request.timeoutMs)
    );
    return {
        ok: verified,
        status: verified ? "postcondition-verified" : "injected-unverified",
        ...result
    };
}

async function setFile(webContents: WebContents, request: Request) {
    if (request.allowMutation !== true) {
        throw new Error("setFile requires allowMutation=true");
    }
    if (typeof request.path !== "string" || !isAbsolute(request.path)) {
        throw new Error("setFile requires an absolute path");
    }

    const stats = statSync(request.path);
    if (!stats.isFile()) {
        throw new Error("setFile path must be a regular file");
    }
    if (stats.size > maxFileBytes) {
        throw new Error("setFile path exceeds the 100 MiB limit");
    }

    const debuggerApi = webContents.debugger;
    const attachedHere = !debuggerApi.isAttached();
    if (attachedHere) {
        debuggerApi.attach("1.3");
    }

    try {
        const document = await debuggerApi.sendCommand("DOM.getDocument", { depth: -1, pierce: true });
        const query = await debuggerApi.sendCommand("DOM.querySelector", {
            nodeId: document.root.nodeId,
            selector: "input[type=file]"
        });
        if (!query.nodeId) {
            return { ok: false, status: "not-injected", reason: "file-input-not-found" };
        }

        await debuggerApi.sendCommand("DOM.setFileInputFiles", {
            nodeId: query.nodeId,
            files: [request.path]
        });

        const expectedName = basename(request.path);
        const verified = await waitUntil(
            async () => await webContents.executeJavaScript(
                `(() => {
                    const expected = ${JSON.stringify(expectedName)};
                    const common = globalThis.Vencord?.Webpack?.Common;
                    const channelId = common?.SelectedChannelStore?.getChannelId?.();
                    const draftType = common?.DraftType?.ChannelMessage;
                    if (
                        channelId != null
                        && draftType != null
                        && common?.UploadAttachmentStore?.getUploads
                    ) {
                        return common.UploadAttachmentStore
                            .getUploads(channelId, draftType)
                            .some(upload => upload.filename === expected && upload.status === "COMPLETED");
                    }
                    const fileInputMatches = Array.from(document.querySelectorAll("input[type=file]"))
                        .some(input => input.files?.[0]?.name === expected);
                    const previewMatches = Array.from(document.querySelectorAll(
                        "[aria-label],[title]"
                    )).some(element => (
                        element.getAttribute("aria-label")?.includes(expected)
                        || element.getAttribute("title")?.includes(expected)
                    ));
                    return fileInputMatches || previewMatches;
                })()`,
                true
            ),
            boundedTimeout(request.timeoutMs, 15_000)
        );

        return {
            ok: verified,
            status: verified ? "postcondition-verified" : "injected-unverified",
            file: expectedName,
            bytes: stats.size
        };
    } finally {
        if (attachedHere && debuggerApi.isAttached()) {
            debuggerApi.detach();
        }
    }
}

async function sendDraft(webContents: WebContents, request: Request) {
    if (request.allowMutation !== true) {
        throw new Error("sendDraft requires allowMutation=true");
    }
    if (
        typeof request.expectedFile !== "string"
        || request.expectedFile.length === 0
        || request.expectedFile.length > 255
    ) {
        throw new Error("sendDraft requires expectedFile");
    }

    const prepared = await webContents.executeJavaScript(`(() => {
        const expected = ${JSON.stringify(request.expectedFile)};
        const visible = element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0 && rect.height > 0
                && style.visibility !== "hidden" && style.display !== "none";
        };
        const editors = Array.from(document.querySelectorAll(
            '[role="textbox"][contenteditable="true"]'
        )).filter(visible);
        const hasExpectedAttachment = Array.from(document.querySelectorAll(
            "[aria-label],[title]"
        )).some(element => (
            element.getAttribute("aria-label")?.includes(expected)
            || element.getAttribute("title")?.includes(expected)
        ));
        if (editors.length !== 1 || !hasExpectedAttachment) {
            return {
                ready: false,
                editorCount: editors.length,
                hasExpectedAttachment
            };
        }
        editors[0].focus();
        return { ready: true };
    })()`, true);

    if (!prepared.ready) {
        return { ok: false, status: "not-injected", reason: "draft-not-ready", ...prepared };
    }

    await webContents.executeJavaScript(`(() => {
        const editor = Array.from(document.querySelectorAll(
            '[role="textbox"][contenteditable="true"]'
        )).find(element => element.getBoundingClientRect().width > 0);
        if (!editor) {
            return false;
        }
        editor.focus();
        return editor.dispatchEvent(new KeyboardEvent("keydown", {
            key: "Enter",
            code: "Enter",
            keyCode: 13,
            which: 13,
            bubbles: true,
            cancelable: true
        }));
    })()`, true);

    await new Promise(resolve => setTimeout(resolve, 250));
    const stillInDraft = await webContents.executeJavaScript(`Array.from(document.querySelectorAll(
        "button,[role=button]"
    )).some(element => (
        element.getAttribute("aria-label") === "Remove Attachment"
        || element.getAttribute("title") === "Remove Attachment"
    ))`, true);

    if (stillInDraft) {
        const debuggerApi = webContents.debugger;
        const attachedHere = !debuggerApi.isAttached();
        if (attachedHere) {
            debuggerApi.attach("1.3");
        }

        try {
            await debuggerApi.sendCommand("Input.dispatchKeyEvent", {
                type: "rawKeyDown",
                key: "Enter",
                code: "Enter",
                windowsVirtualKeyCode: 13,
                nativeVirtualKeyCode: 13
            });
            await debuggerApi.sendCommand("Input.dispatchKeyEvent", {
                type: "keyUp",
                key: "Enter",
                code: "Enter",
                windowsVirtualKeyCode: 13,
                nativeVirtualKeyCode: 13
            });
        } finally {
            if (attachedHere && debuggerApi.isAttached()) {
                debuggerApi.detach();
            }
        }
    }

    const verified = await waitUntil(
        async () => await webContents.executeJavaScript(`(() => {
            const expected = ${JSON.stringify(request.expectedFile)};
            const attachmentStillInDraft = Array.from(document.querySelectorAll(
                "button,[role=button]"
            )).some(element => (
                element.getAttribute("aria-label") === "Remove Attachment"
                || element.getAttribute("title") === "Remove Attachment"
            ));
            const sentAttachment = Array.from(document.querySelectorAll(
                '[data-list-item-id^="chat-messages"],[id^="chat-messages"]'
            )).some(message => Array.from(message.querySelectorAll(
                "a[href],img[src],[aria-label],[title]"
            )).some(element => (
                element.getAttribute("href")?.includes(encodeURIComponent(expected))
                || element.getAttribute("href")?.includes(expected)
                || element.getAttribute("src")?.includes(encodeURIComponent(expected))
                || element.getAttribute("src")?.includes(expected)
                || element.getAttribute("aria-label")?.includes(expected)
                || element.getAttribute("title")?.includes(expected)
            )));
            return !attachmentStillInDraft && sentAttachment;
        })()`, true),
        boundedTimeout(request.timeoutMs, 15_000)
    );

    return {
        ok: verified,
        status: verified ? "postcondition-verified" : "injected-unverified",
        file: request.expectedFile
    };
}

async function dispatch(webContents: WebContents, request: Request) {
    switch (request.action) {
        case "inspect":
            return { ok: true, status: "observed", ...(await inspect(webContents)) };
        case "waitForText": {
            if (typeof request.text !== "string" || request.text.length === 0) {
                throw new Error("waitForText requires text");
            }
            const verified = await waitForText(webContents, request.text, boundedTimeout(request.timeoutMs));
            return {
                ok: verified,
                status: verified ? "postcondition-verified" : "not-observed",
                expected: request.text
            };
        }
        case "waitForTitle": {
            if (typeof request.regex !== "string" || request.regex.length === 0) {
                throw new Error("waitForTitle requires regex");
            }
            const verified = await waitForTitle(webContents, request.regex, boundedTimeout(request.timeoutMs));
            return {
                ok: verified,
                status: verified ? "postcondition-verified" : "not-observed",
                expected: request.regex
            };
        }
        case "click":
            return await click(webContents, request);
        case "navigateToNamedChannel":
            return await navigateToNamedChannel(webContents, request);
        case "setFile":
            return await setFile(webContents, request);
        case "sendDraft":
            return await sendDraft(webContents, request);
        default:
            throw new Error(`unsupported action: ${String(request.action)}`);
    }
}

function attachServerListener(webContents: WebContents) {
    if (!server) {
        return;
    }

    server.removeAllListeners("connection");
    server.on("connection", socket => {
        let buffer = "";
        let handled = false;

        socket.setEncoding("utf8");
        socket.on("data", chunk => {
            if (handled) {
                return;
            }

            buffer += chunk;
            if (Buffer.byteLength(buffer, "utf8") > maxRequestBytes) {
                handled = true;
                writeResponse(socket, { ok: false, status: "rejected", error: "request-too-large" });
                return;
            }

            const newline = buffer.indexOf("\n");
            if (newline === -1) {
                return;
            }

            handled = true;
            const raw = buffer.slice(0, newline);
            void (async () => {
                try {
                    const request = JSON.parse(raw) as Request;
                    if (!request || typeof request !== "object" || typeof request.action !== "string") {
                        throw new Error("request must contain an action");
                    }
                    writeResponse(socket, await dispatch(webContents, request));
                } catch (error) {
                    writeResponse(socket, {
                        ok: false,
                        status: "error",
                        error: error instanceof Error ? error.message : String(error)
                    });
                }
            })();
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

    attachServerListener(event.sender);
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
