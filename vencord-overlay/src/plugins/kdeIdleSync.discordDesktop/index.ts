/*
 * Vencord, a Discord client mod
 * Copyright (c) 2026 Vendicated and contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import { definePluginSettings } from "@api/Settings";
import { getUserSettingLazy } from "@api/UserSettings";
import { Devs } from "@utils/constants";
import definePlugin, { OptionType, PluginNative } from "@utils/types";

const Native = VencordNative.pluginHelpers.KdeIdleSync as PluginNative<typeof import("./native")>;
const StatusSettings = getUserSettingLazy<string>("status", "status")!;

type ManagedStatus = "online" | "idle" | "dnd" | "invisible";

let savedStatus: string | null = null;

const settings = definePluginSettings({
    inactiveStatus: {
        type: OptionType.SELECT,
        description: "Status to apply when KDE reports you idle or locked",
        options: [
            { label: "Idle", value: "idle", default: true },
            { label: "Invisible", value: "invisible" },
            { label: "Do Not Disturb", value: "dnd" },
            { label: "Online", value: "online" }
        ]
    },
    restoreStatusOnActive: {
        type: OptionType.BOOLEAN,
        description: "Restore your previous status when activity resumes",
        default: true
    }
});

function getCurrentStatus() {
    return StatusSettings.getSetting();
}

function setStatus(status: ManagedStatus) {
    StatusSettings.updateSetting(status);
}

export default definePlugin({
    name: "KdeIdleSync",
    description: "Sync your Discord status with KDE lock and idle state via a local watcher service",
    authors: [Devs.newwares],
    enabledByDefault: true,
    requiresRestart: false,
    settings,

    start() {
        Native.startServer();
    },

    stop() {
        Native.stopServer();
    },

    handleExternalState(state: "active" | "inactive") {
        if (state === "inactive") {
            this.applyInactiveState();
        } else {
            this.applyActiveState();
        }
    },

    applyInactiveState() {
        const current = getCurrentStatus();
        const inactiveStatus = settings.store.inactiveStatus as ManagedStatus;

        if (current === inactiveStatus) {
            return;
        }

        if (savedStatus == null) {
            savedStatus = current;
        }

        setStatus(inactiveStatus);
    },

    applyActiveState() {
        if (!settings.store.restoreStatusOnActive) {
            savedStatus = null;
            return;
        }

        const inactiveStatus = settings.store.inactiveStatus as ManagedStatus;
        const current = getCurrentStatus();

        if (savedStatus != null && current === inactiveStatus) {
            setStatus(savedStatus as ManagedStatus);
        }

        savedStatus = null;
    }
});
