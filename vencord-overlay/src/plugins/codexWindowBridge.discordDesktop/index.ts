/*
 * Vencord, a Discord client mod
 * Copyright (c) 2026 Vendicated and contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import { Devs } from "@utils/constants";
import definePlugin, { PluginNative } from "@utils/types";

const Native = VencordNative.pluginHelpers.CodexWindowBridge as PluginNative<typeof import("./native")>;

export default definePlugin({
    name: "CodexWindowBridge",
    description: "Expose narrow, local-only Discord window controls to Codex over a protected Unix socket",
    authors: [Devs.newwares],
    enabledByDefault: false,
    requiresRestart: false,

    start() {
        Native.startServer();
    },

    stop() {
        Native.stopServer();
    }
});
