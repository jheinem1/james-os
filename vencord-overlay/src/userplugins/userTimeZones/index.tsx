/*
 * Vencord, a Discord client mod
 * Copyright (c) 2026 Vendicated and contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import "./styles.css";

import { definePluginSettings, SettingsStore } from "@api/Settings";
import { Heading } from "@components/Heading";
import { Margins } from "@utils/margins";
import definePlugin from "@utils/types";
import { RenderModalProps } from "@vencord/discord-types";
import { findComponentByCodeLazy } from "@webpack";
import { Modal, openModal, React, TextInput, Tooltip, useEffect, useMemo, UserStore, useState } from "@webpack/common";

type EntryMode = "iana" | "fixedOffset";
type EditorMode = "city" | "offset";

interface TimeZoneEntry {
    userId: string;
    label?: string;
    mode: EntryMode;
    timeZone?: string;
    offsetMinutes?: number;
    observesDst?: boolean;
    updatedAt: number;
}

interface CityOption {
    label: string;
    region: string;
    timeZone: string;
}

const cl = (name: string) => `vc-user-time-zones-${name}`;
const settings = definePluginSettings({}).withPrivateSettings<{
    entries?: Record<string, TimeZoneEntry>;
}>();

const Section = findComponentByCodeLazy("headingVariant:", '"section"', "headingIcon:");
const listeners = new Set<() => void>();

const fallbackTimeZones = [
    "America/Los_Angeles",
    "America/Denver",
    "America/Phoenix",
    "America/Chicago",
    "America/New_York",
    "America/Sao_Paulo",
    "UTC",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Athens",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Bangkok",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Australia/Sydney",
];

const cityAliases: CityOption[] = [
    // United States
    { label: "San Francisco", region: "California, United States", timeZone: "America/Los_Angeles" },
    { label: "Oakland", region: "California, United States", timeZone: "America/Los_Angeles" },
    { label: "San Jose", region: "California, United States", timeZone: "America/Los_Angeles" },
    { label: "Sacramento", region: "California, United States", timeZone: "America/Los_Angeles" },
    { label: "Los Angeles", region: "California, United States", timeZone: "America/Los_Angeles" },
    { label: "San Diego", region: "California, United States", timeZone: "America/Los_Angeles" },
    { label: "Seattle", region: "Washington, United States", timeZone: "America/Los_Angeles" },
    { label: "Portland", region: "Oregon, United States", timeZone: "America/Los_Angeles" },
    { label: "Las Vegas", region: "Nevada, United States", timeZone: "America/Los_Angeles" },
    { label: "Denver", region: "Colorado, United States", timeZone: "America/Denver" },
    { label: "Salt Lake City", region: "Utah, United States", timeZone: "America/Denver" },
    { label: "Albuquerque", region: "New Mexico, United States", timeZone: "America/Denver" },
    { label: "El Paso", region: "Texas, United States", timeZone: "America/Denver" },
    { label: "Boise", region: "Idaho, United States", timeZone: "America/Boise" },
    { label: "Phoenix", region: "Arizona, United States", timeZone: "America/Phoenix" },
    { label: "Tucson", region: "Arizona, United States", timeZone: "America/Phoenix" },
    { label: "Chicago", region: "Illinois, United States", timeZone: "America/Chicago" },
    { label: "Dallas", region: "Texas, United States", timeZone: "America/Chicago" },
    { label: "Houston", region: "Texas, United States", timeZone: "America/Chicago" },
    { label: "Austin", region: "Texas, United States", timeZone: "America/Chicago" },
    { label: "San Antonio", region: "Texas, United States", timeZone: "America/Chicago" },
    { label: "Minneapolis", region: "Minnesota, United States", timeZone: "America/Chicago" },
    { label: "St. Louis", region: "Missouri, United States", timeZone: "America/Chicago" },
    { label: "Kansas City", region: "Missouri, United States", timeZone: "America/Chicago" },
    { label: "New Orleans", region: "Louisiana, United States", timeZone: "America/Chicago" },
    { label: "Nashville", region: "Tennessee, United States", timeZone: "America/Chicago" },
    { label: "Memphis", region: "Tennessee, United States", timeZone: "America/Chicago" },
    { label: "Milwaukee", region: "Wisconsin, United States", timeZone: "America/Chicago" },
    { label: "Omaha", region: "Nebraska, United States", timeZone: "America/Chicago" },
    { label: "Oklahoma City", region: "Oklahoma, United States", timeZone: "America/Chicago" },
    { label: "New York", region: "New York, United States", timeZone: "America/New_York" },
    { label: "Boston", region: "Massachusetts, United States", timeZone: "America/New_York" },
    { label: "Washington, D.C.", region: "District of Columbia, United States", timeZone: "America/New_York" },
    { label: "Philadelphia", region: "Pennsylvania, United States", timeZone: "America/New_York" },
    { label: "Miami", region: "Florida, United States", timeZone: "America/New_York" },
    { label: "Atlanta", region: "Georgia, United States", timeZone: "America/New_York" },
    { label: "Detroit", region: "Michigan, United States", timeZone: "America/New_York" },
    { label: "Cleveland", region: "Ohio, United States", timeZone: "America/New_York" },
    { label: "Columbus", region: "Ohio, United States", timeZone: "America/New_York" },
    { label: "Pittsburgh", region: "Pennsylvania, United States", timeZone: "America/New_York" },
    { label: "Charlotte", region: "North Carolina, United States", timeZone: "America/New_York" },
    { label: "Raleigh", region: "North Carolina, United States", timeZone: "America/New_York" },
    { label: "Orlando", region: "Florida, United States", timeZone: "America/New_York" },
    { label: "Tampa", region: "Florida, United States", timeZone: "America/New_York" },
    { label: "Baltimore", region: "Maryland, United States", timeZone: "America/New_York" },
    { label: "Indianapolis", region: "Indiana, United States", timeZone: "America/Indiana/Indianapolis" },
    { label: "Louisville", region: "Kentucky, United States", timeZone: "America/Kentucky/Louisville" },
    { label: "Anchorage", region: "Alaska, United States", timeZone: "America/Anchorage" },
    { label: "Honolulu", region: "Hawaii, United States", timeZone: "Pacific/Honolulu" },

    // Canada, Mexico, Central America, and the Caribbean
    { label: "Vancouver", region: "British Columbia, Canada", timeZone: "America/Vancouver" },
    { label: "Calgary", region: "Alberta, Canada", timeZone: "America/Edmonton" },
    { label: "Edmonton", region: "Alberta, Canada", timeZone: "America/Edmonton" },
    { label: "Winnipeg", region: "Manitoba, Canada", timeZone: "America/Winnipeg" },
    { label: "Toronto", region: "Ontario, Canada", timeZone: "America/Toronto" },
    { label: "Ottawa", region: "Ontario, Canada", timeZone: "America/Toronto" },
    { label: "Montreal", region: "Quebec, Canada", timeZone: "America/Toronto" },
    { label: "Halifax", region: "Nova Scotia, Canada", timeZone: "America/Halifax" },
    { label: "St. John's", region: "Newfoundland and Labrador, Canada", timeZone: "America/St_Johns" },
    { label: "Tijuana", region: "Baja California, Mexico", timeZone: "America/Tijuana" },
    { label: "Mexico City", region: "Mexico", timeZone: "America/Mexico_City" },
    { label: "Cancun", region: "Quintana Roo, Mexico", timeZone: "America/Cancun" },
    { label: "Guatemala City", region: "Guatemala", timeZone: "America/Guatemala" },
    { label: "San Jose", region: "Costa Rica", timeZone: "America/Costa_Rica" },
    { label: "Panama City", region: "Panama", timeZone: "America/Panama" },
    { label: "Havana", region: "Cuba", timeZone: "America/Havana" },
    { label: "Kingston", region: "Jamaica", timeZone: "America/Jamaica" },
    { label: "San Juan", region: "Puerto Rico", timeZone: "America/Puerto_Rico" },

    // South America
    { label: "Bogota", region: "Colombia", timeZone: "America/Bogota" },
    { label: "Lima", region: "Peru", timeZone: "America/Lima" },
    { label: "Quito", region: "Ecuador", timeZone: "America/Guayaquil" },
    { label: "Caracas", region: "Venezuela", timeZone: "America/Caracas" },
    { label: "La Paz", region: "Bolivia", timeZone: "America/La_Paz" },
    { label: "Santiago", region: "Chile", timeZone: "America/Santiago" },
    { label: "Buenos Aires", region: "Argentina", timeZone: "America/Argentina/Buenos_Aires" },
    { label: "Montevideo", region: "Uruguay", timeZone: "America/Montevideo" },
    { label: "Sao Paulo", region: "Brazil", timeZone: "America/Sao_Paulo" },
    { label: "Rio de Janeiro", region: "Brazil", timeZone: "America/Sao_Paulo" },

    // Europe
    { label: "London", region: "United Kingdom", timeZone: "Europe/London" },
    { label: "Manchester", region: "United Kingdom", timeZone: "Europe/London" },
    { label: "Birmingham", region: "United Kingdom", timeZone: "Europe/London" },
    { label: "Glasgow", region: "United Kingdom", timeZone: "Europe/London" },
    { label: "Dublin", region: "Ireland", timeZone: "Europe/Dublin" },
    { label: "Lisbon", region: "Portugal", timeZone: "Europe/Lisbon" },
    { label: "Madrid", region: "Spain", timeZone: "Europe/Madrid" },
    { label: "Barcelona", region: "Spain", timeZone: "Europe/Madrid" },
    { label: "Paris", region: "France", timeZone: "Europe/Paris" },
    { label: "Brussels", region: "Belgium", timeZone: "Europe/Brussels" },
    { label: "Amsterdam", region: "Netherlands", timeZone: "Europe/Amsterdam" },
    { label: "Berlin", region: "Germany", timeZone: "Europe/Berlin" },
    { label: "Hamburg", region: "Germany", timeZone: "Europe/Berlin" },
    { label: "Munich", region: "Germany", timeZone: "Europe/Berlin" },
    { label: "Frankfurt", region: "Germany", timeZone: "Europe/Berlin" },
    { label: "Zurich", region: "Switzerland", timeZone: "Europe/Zurich" },
    { label: "Geneva", region: "Switzerland", timeZone: "Europe/Zurich" },
    { label: "Rome", region: "Italy", timeZone: "Europe/Rome" },
    { label: "Milan", region: "Italy", timeZone: "Europe/Rome" },
    { label: "Vienna", region: "Austria", timeZone: "Europe/Vienna" },
    { label: "Prague", region: "Czechia", timeZone: "Europe/Prague" },
    { label: "Warsaw", region: "Poland", timeZone: "Europe/Warsaw" },
    { label: "Copenhagen", region: "Denmark", timeZone: "Europe/Copenhagen" },
    { label: "Oslo", region: "Norway", timeZone: "Europe/Oslo" },
    { label: "Stockholm", region: "Sweden", timeZone: "Europe/Stockholm" },
    { label: "Helsinki", region: "Finland", timeZone: "Europe/Helsinki" },
    { label: "Athens", region: "Greece", timeZone: "Europe/Athens" },
    { label: "Bucharest", region: "Romania", timeZone: "Europe/Bucharest" },
    { label: "Istanbul", region: "Turkey", timeZone: "Europe/Istanbul" },
    { label: "Kyiv", region: "Ukraine", timeZone: "Europe/Kyiv" },
    { label: "Moscow", region: "Russia", timeZone: "Europe/Moscow" },

    // Africa and the Middle East
    { label: "Casablanca", region: "Morocco", timeZone: "Africa/Casablanca" },
    { label: "Cairo", region: "Egypt", timeZone: "Africa/Cairo" },
    { label: "Lagos", region: "Nigeria", timeZone: "Africa/Lagos" },
    { label: "Nairobi", region: "Kenya", timeZone: "Africa/Nairobi" },
    { label: "Johannesburg", region: "South Africa", timeZone: "Africa/Johannesburg" },
    { label: "Cape Town", region: "South Africa", timeZone: "Africa/Johannesburg" },
    { label: "Jerusalem", region: "Israel", timeZone: "Asia/Jerusalem" },
    { label: "Beirut", region: "Lebanon", timeZone: "Asia/Beirut" },
    { label: "Dubai", region: "United Arab Emirates", timeZone: "Asia/Dubai" },
    { label: "Riyadh", region: "Saudi Arabia", timeZone: "Asia/Riyadh" },
    { label: "Tehran", region: "Iran", timeZone: "Asia/Tehran" },

    // Asia
    { label: "Karachi", region: "Pakistan", timeZone: "Asia/Karachi" },
    { label: "Delhi", region: "India", timeZone: "Asia/Kolkata" },
    { label: "Mumbai", region: "India", timeZone: "Asia/Kolkata" },
    { label: "Bengaluru", region: "India", timeZone: "Asia/Kolkata" },
    { label: "Chennai", region: "India", timeZone: "Asia/Kolkata" },
    { label: "Hyderabad", region: "India", timeZone: "Asia/Kolkata" },
    { label: "Kolkata", region: "India", timeZone: "Asia/Kolkata" },
    { label: "Kathmandu", region: "Nepal", timeZone: "Asia/Kathmandu" },
    { label: "Dhaka", region: "Bangladesh", timeZone: "Asia/Dhaka" },
    { label: "Colombo", region: "Sri Lanka", timeZone: "Asia/Colombo" },
    { label: "Bangkok", region: "Thailand", timeZone: "Asia/Bangkok" },
    { label: "Ho Chi Minh City", region: "Vietnam", timeZone: "Asia/Ho_Chi_Minh" },
    { label: "Jakarta", region: "Indonesia", timeZone: "Asia/Jakarta" },
    { label: "Singapore", region: "Singapore", timeZone: "Asia/Singapore" },
    { label: "Kuala Lumpur", region: "Malaysia", timeZone: "Asia/Kuala_Lumpur" },
    { label: "Manila", region: "Philippines", timeZone: "Asia/Manila" },
    { label: "Hong Kong", region: "Hong Kong", timeZone: "Asia/Hong_Kong" },
    { label: "Beijing", region: "China", timeZone: "Asia/Shanghai" },
    { label: "Shanghai", region: "China", timeZone: "Asia/Shanghai" },
    { label: "Guangzhou", region: "China", timeZone: "Asia/Shanghai" },
    { label: "Shenzhen", region: "China", timeZone: "Asia/Shanghai" },
    { label: "Taipei", region: "Taiwan", timeZone: "Asia/Taipei" },
    { label: "Seoul", region: "South Korea", timeZone: "Asia/Seoul" },
    { label: "Tokyo", region: "Japan", timeZone: "Asia/Tokyo" },
    { label: "Osaka", region: "Japan", timeZone: "Asia/Tokyo" },

    // Oceania
    { label: "Perth", region: "Western Australia, Australia", timeZone: "Australia/Perth" },
    { label: "Adelaide", region: "South Australia, Australia", timeZone: "Australia/Adelaide" },
    { label: "Brisbane", region: "Queensland, Australia", timeZone: "Australia/Brisbane" },
    { label: "Sydney", region: "New South Wales, Australia", timeZone: "Australia/Sydney" },
    { label: "Melbourne", region: "Victoria, Australia", timeZone: "Australia/Melbourne" },
    { label: "Hobart", region: "Tasmania, Australia", timeZone: "Australia/Hobart" },
    { label: "Auckland", region: "New Zealand", timeZone: "Pacific/Auckland" },
    { label: "Wellington", region: "New Zealand", timeZone: "Pacific/Auckland" },
    { label: "Suva", region: "Fiji", timeZone: "Pacific/Fiji" },
];

const regionSearchAliases: Record<string, string> = {
    Alabama: "al", Alaska: "ak", Arizona: "az", Arkansas: "ar", California: "ca",
    Colorado: "co", Connecticut: "ct", Delaware: "de", Florida: "fl", Georgia: "ga",
    Hawaii: "hi", Idaho: "id", Illinois: "il", Indiana: "in", Iowa: "ia", Kansas: "ks",
    Kentucky: "ky", Louisiana: "la", Maine: "me", Maryland: "md", Massachusetts: "ma",
    Michigan: "mi", Minnesota: "mn", Mississippi: "ms", Missouri: "mo", Montana: "mt",
    Nebraska: "ne", Nevada: "nv", "New Hampshire": "nh", "New Jersey": "nj",
    "New Mexico": "nm", "New York": "ny", "North Carolina": "nc", "North Dakota": "nd",
    Ohio: "oh", Oklahoma: "ok", Oregon: "or", Pennsylvania: "pa", "Rhode Island": "ri",
    "South Carolina": "sc", "South Dakota": "sd", Tennessee: "tn", Texas: "tx", Utah: "ut",
    Vermont: "vt", Virginia: "va", Washington: "wa", "West Virginia": "wv", Wisconsin: "wi",
    Wyoming: "wy", "District of Columbia": "dc",
    "United States": "us usa america", "United Kingdom": "uk gb britain", Canada: "can",
    Australia: "au aus", "New Zealand": "nz", "United Arab Emirates": "uae",
    "South Korea": "korea rok", China: "prc", Taiwan: "tw", Japan: "jp",
};

function getEntries() {
    return settings.plain.entries ?? {};
}

function notifyEntryListeners() {
    for (const listener of listeners) listener();
}

function saveEntry(entry: TimeZoneEntry) {
    settings.store.entries = {
        ...getEntries(),
        [entry.userId]: entry
    };
    SettingsStore.markAsChanged();
    notifyEntryListeners();
}

function deleteEntry(userId: string) {
    const next = { ...getEntries() };
    delete next[userId];
    settings.store.entries = next;
    SettingsStore.markAsChanged();
    notifyEntryListeners();
}

function useUserTimeZoneEntry(userId: string) {
    const [entry, setEntry] = useState(getEntries()[userId]);

    useEffect(() => {
        const listener = () => setEntry(getEntries()[userId]);
        listeners.add(listener);
        listener();
        return () => void listeners.delete(listener);
    }, [userId]);

    return entry;
}

function getCityOptions() {
    const intl = Intl as typeof Intl & { supportedValuesOf?: (key: "timeZone") => string[]; };
    const canonicalOptions = Array.from(new Set([...fallbackTimeZones, ...(intl.supportedValuesOf?.("timeZone") ?? [])]))
        .map(timeZone => ({
            label: getCityLabel(timeZone),
            region: getRegionLabel(timeZone),
            timeZone
        }));
    const seen = new Set<string>();

    return [...cityAliases, ...canonicalOptions].filter(option => {
        const key = `${option.label.toLowerCase()}\0${option.timeZone}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}

function normalizeLocationSearch(value: string) {
    return value
        .normalize("NFKD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .trim();
}

function getRegionAliases(region: string) {
    const normalizedRegion = normalizeLocationSearch(region);
    return Object.entries(regionSearchAliases)
        .filter(([name]) => normalizedRegion.includes(normalizeLocationSearch(name)))
        .flatMap(([, aliases]) => aliases.split(" "));
}

function matchesCitySearch(option: CityOption, query: string) {
    const queryTerms = normalizeLocationSearch(query).split(" ").filter(Boolean);
    if (!queryTerms.length) return true;

    const locationTerms = normalizeLocationSearch(`${option.label} ${option.region} ${option.timeZone}`).split(" ");
    const aliasTerms = getRegionAliases(option.region);

    return queryTerms.every(queryTerm => {
        const locationMatches = queryTerm.length <= 2
            ? locationTerms.includes(queryTerm)
            : locationTerms.some(locationTerm => locationTerm.startsWith(queryTerm));

        return locationMatches || aliasTerms.includes(queryTerm);
    });
}

function getCityLabel(timeZone: string) {
    return timeZone.replace(/_/g, " ").split("/").at(-1) ?? timeZone;
}

function getRegionLabel(timeZone: string) {
    const pieces = timeZone.replace(/_/g, " ").split("/");
    if (pieces.length === 1) return pieces[0];
    return pieces.slice(0, -1).join(" · ");
}

function getLocationLabel(entry: TimeZoneEntry) {
    if (entry.mode === "iana" && entry.timeZone) return entry.label || getCityLabel(entry.timeZone);
    return formatOffset(entry.offsetMinutes ?? 0);
}

function formatOffset(offsetMinutes: number) {
    if (offsetMinutes === 0) return "UTC";

    const sign = offsetMinutes > 0 ? "+" : "-";
    const abs = Math.abs(offsetMinutes);
    const hours = Math.floor(abs / 60);
    const minutes = abs % 60;

    return `UTC${sign}${hours}${minutes ? `:${minutes.toString().padStart(2, "0")}` : ""}`;
}

function offsetOptions() {
    const options = [] as { label: string; value: number; }[];
    for (let offset = -12 * 60; offset <= 14 * 60; offset += 15) {
        options.push({ label: formatOffset(offset), value: offset });
    }
    return options;
}

function filteredOffsetOptions(query: string) {
    const normalized = query.toLowerCase().replace(/\s/g, "");
    const options = offsetOptions();

    if (!normalized) return options;
    return options.filter(option => option.label.toLowerCase().replace(/\s/g, "").includes(normalized));
}

function parseOffsetInput(query: string) {
    const normalized = query.trim().toUpperCase().replace(/\s/g, "");
    if (normalized === "UTC" || normalized === "GMT" || normalized === "0") return 0;

    const match = /^(?:UTC|GMT)?([+-])(\d{1,2})(?::?([0-5]\d))?$/.exec(normalized);
    if (!match) return null;

    const hours = Number(match[2]);
    const minutes = Number(match[3] ?? "0");
    if (hours > 14 || (hours === 14 && minutes > 0)) return null;

    const offset = hours * 60 + minutes;
    return match[1] === "+" ? offset : -offset;
}

function formatIanaTime(timeZone: string) {
    return new Intl.DateTimeFormat(undefined, {
        hour: "numeric",
        minute: "2-digit",
        timeZone
    }).format(new Date());
}

function formatFixedOffsetTime(offsetMinutes: number) {
    const shifted = new Date(Date.now() + offsetMinutes * 60_000);
    return new Intl.DateTimeFormat(undefined, {
        hour: "numeric",
        minute: "2-digit",
        timeZone: "UTC"
    }).format(shifted);
}

function getTimeForEntry(entry: TimeZoneEntry) {
    if (entry.mode === "iana" && entry.timeZone) return formatIanaTime(entry.timeZone);
    if (entry.mode === "fixedOffset" && typeof entry.offsetMinutes === "number") return formatFixedOffsetTime(entry.offsetMinutes);
    return null;
}

function getDetailsForEntry(entry: TimeZoneEntry) {
    if (entry.mode === "iana" && entry.timeZone) {
        return `${entry.label || getCityLabel(entry.timeZone)} · ${entry.timeZone} · regional daylight-saving rules`;
    }
    return `${formatOffset(entry.offsetMinutes ?? 0)} · fixed offset`;
}

function useClockTick() {
    const [, setTick] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => setTick(tick => tick + 1), 30_000);
        return () => clearInterval(interval);
    }, []);
}

function ClockIcon({ size = 14 }: { size?: number; }) {
    return (
        <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5a1 1 0 1 0-2 0v5c0 .27.1.52.3.7l3 3a1 1 0 0 0 1.4-1.4L13 11.58V7Z" />
        </svg>
    );
}

function openEditor(userId: string) {
    openModal(props => (
        <UserTimeZoneModal
            rootProps={props}
            userId={userId}
        />
    ));
}

function ModeButton({ mode, activeMode, setMode, children }: {
    mode: EditorMode;
    activeMode: EditorMode;
    setMode(mode: EditorMode): void;
    children: React.ReactNode;
}) {
    return (
        <button
            type="button"
            aria-pressed={mode === activeMode}
            className={`${cl("mode-button")} ${mode === activeMode ? cl("mode-button-active") : ""}`}
            onClick={() => setMode(mode)}
        >
            {children}
        </button>
    );
}

function UserTimeZoneModal({ rootProps, userId }: { rootProps: RenderModalProps; userId: string; }) {
    useClockTick();

    const user = UserStore.getUser(userId);
    const displayName = user?.globalName || user?.username || "This user";
    const existing = getEntries()[userId];
    const localTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    const initialTimeZone = existing?.mode === "iana" && existing.timeZone ? existing.timeZone : localTimeZone;
    const initialCity: CityOption = {
        label: existing?.mode === "iana" && existing.label ? existing.label : getCityLabel(initialTimeZone),
        region: getRegionLabel(initialTimeZone),
        timeZone: initialTimeZone
    };
    const cityOptions = useMemo(getCityOptions, []);
    const [mode, setMode] = useState<EditorMode>(existing?.mode === "fixedOffset" ? "offset" : "city");
    const [selectedCity, setSelectedCity] = useState<CityOption | null>(initialCity);
    const [cityQuery, setCityQuery] = useState(initialCity.label);
    const [offsetQuery, setOffsetQuery] = useState(formatOffset(existing?.offsetMinutes ?? 0));

    const cityMatches = useMemo(() => {
        const zones = cityOptions.filter(option => matchesCitySearch(option, cityQuery));

        return zones.slice(0, 24);
    }, [cityOptions, cityQuery]);

    const offsetMatches = useMemo(() => filteredOffsetOptions(offsetQuery).slice(0, 40), [offsetQuery]);
    const parsedOffset = parseOffsetInput(offsetQuery);
    const previewEntry = mode === "city"
        ? selectedCity ? {
            userId,
            mode: "iana" as const,
            label: selectedCity.label,
            timeZone: selectedCity.timeZone,
            updatedAt: Date.now()
        } : null
        : parsedOffset != null ? {
            userId,
            mode: "fixedOffset" as const,
            offsetMinutes: parsedOffset,
            updatedAt: Date.now()
        } : null;
    const previewTime = previewEntry && getTimeForEntry(previewEntry);
    const canSave = previewEntry != null;

    const save = () => {
        if (!previewEntry) return;
        saveEntry(previewEntry);
        rootProps.onClose();
    };

    const reset = () => {
        deleteEntry(userId);
        rootProps.onClose();
    };

    return (
        <Modal
            {...rootProps}
            size="md"
            title="Set local time"
            subtitle={`For ${displayName}`}
            actions={[
                ...(existing ? [{
                    text: "Remove",
                    variant: "critical-primary" as const,
                    onClick: reset
                }] : []),
                {
                    text: "Cancel",
                    variant: "secondary",
                    onClick: rootProps.onClose
                },
                {
                    text: "Save local time",
                    variant: "primary",
                    disabled: !canSave,
                    onClick: save
                }
            ]}
        >
            <div className={cl("modal-content")}>
                <div className={`${cl("preview-card")} ${!previewEntry ? cl("preview-card-empty") : ""}`}>
                    <span className={cl("preview-icon")}><ClockIcon size={20} /></span>
                    <div className={cl("preview-copy")}>
                        <span className={cl("preview-eyebrow")}>CURRENT LOCAL TIME</span>
                        <strong>{previewTime ?? "Choose a location"}</strong>
                        <span>{previewEntry ? getDetailsForEntry(previewEntry) : "Search by location or enter a UTC offset below."}</span>
                    </div>
                </div>

                <div className={cl("mode-row")}>
                    <ModeButton mode="city" activeMode={mode} setMode={setMode}>City or region</ModeButton>
                    <ModeButton mode="offset" activeMode={mode} setMode={setMode}>UTC offset</ModeButton>
                </div>

                {mode === "city" && (
                    <div>
                        <Heading tag="h5" className={Margins.bottom8}>Search by city, state, or country</Heading>
                        <TextInput
                            value={cityQuery}
                            placeholder="Try San Francisco, Utah, or Japan"
                            onChange={value => {
                                setCityQuery(value);
                                setSelectedCity(null);
                            }}
                        />
                        <div className={cl("field-hint")}>Choose a nearby city so daylight-saving changes stay automatic.</div>
                        <div className={cl("choice-list")}>
                            {cityMatches.map(option => (
                                <button
                                    type="button"
                                    key={`${option.label}:${option.timeZone}`}
                                    className={`${cl("choice")} ${option.label === selectedCity?.label && option.timeZone === selectedCity.timeZone ? cl("choice-active") : ""}`}
                                    onClick={() => {
                                        setSelectedCity(option);
                                        setCityQuery(option.label);
                                    }}
                                >
                                    <span className={cl("choice-copy")}>
                                        <strong>{option.label}</strong>
                                        <small>{option.region}</small>
                                    </span>
                                    <span className={cl("choice-time")}>{formatIanaTime(option.timeZone)}</span>
                                </button>
                            ))}
                            {!cityMatches.length && (
                                <div className={cl("empty-state")}>No matching location. Try a nearby city, state, country, or UTC offset.</div>
                            )}
                        </div>
                    </div>
                )}

                {mode === "offset" && (
                    <div>
                        <Heading tag="h5" className={Margins.bottom8}>Fixed UTC offset</Heading>
                        <TextInput
                            value={offsetQuery}
                            placeholder="UTC-7 or +05:30"
                            onChange={setOffsetQuery}
                        />
                        <div className={`${cl("field-hint")} ${parsedOffset == null ? cl("field-error") : ""}`}>
                            {parsedOffset == null
                                ? "Enter an offset from UTC-12 through UTC+14."
                                : "Fixed offsets do not change automatically for daylight saving."}
                        </div>
                        <div className={cl("choice-list")}>
                            {offsetMatches.map(option => (
                                <button
                                    type="button"
                                    key={option.value}
                                    className={`${cl("choice")} ${option.value === parsedOffset ? cl("choice-active") : ""}`}
                                    onClick={() => setOffsetQuery(option.label)}
                                >
                                    <span className={cl("choice-copy")}><strong>{option.label}</strong></span>
                                    <span className={cl("choice-time")}>{formatFixedOffsetTime(option.value)}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

            </div>
        </Modal>
    );
}

function TimeZoneSection({ userId, isSidebar }: { userId: string; isSidebar: boolean; }) {
    useClockTick();

    const entry = useUserTimeZoneEntry(userId);
    const time = entry && getTimeForEntry(entry);
    const location = entry && getLocationLabel(entry);
    const details = entry && getDetailsForEntry(entry);

    const body = (
        <button
            type="button"
            className={isSidebar ? cl("sidebar-button") : cl("profile-button")}
            onClick={() => openEditor(userId)}
        >
            <span className={cl("profile-button-content")}>
                <span className={cl("profile-clock")}><ClockIcon size={16} /></span>
                <span className={cl("profile-copy")}>
                    <strong>{time ?? "Set local time"}</strong>
                    <small>{location ?? "Add this user's city or UTC offset"}</small>
                </span>
                <span className={cl("edit-label")}>{entry ? "Edit" : "Set"}</span>
            </span>
        </button>
    );

    return (
        <Section
            heading="Current local time"
            headingVariant={isSidebar ? "text-xs/semibold" : "text-xs/medium"}
            headingColor={isSidebar ? "text-strong" : "text-default"}
            className={isSidebar ? undefined : cl("profile-section")}
        >
            {details ? (
                <Tooltip text={details}>
                    {props => <span {...props}>{body}</span>}
                </Tooltip>
            ) : body}
        </Section>
    );
}

function MessageLocalTime({ userId }: { userId: string; }) {
    useClockTick();
    const entry = useUserTimeZoneEntry(userId);
    const time = entry && getTimeForEntry(entry);
    const details = entry && getDetailsForEntry(entry);

    if (!time || !details) return null;

    return (
        <Tooltip text={`Current local time: ${time} · ${details}`}>
            {tooltipProps => (
                <button
                    {...tooltipProps}
                    type="button"
                    aria-label={`Current local time ${time}`}
                    className={cl("message-time")}
                    onClick={event => {
                        event.stopPropagation();
                        openEditor(userId);
                    }}
                >
                    <ClockIcon size={12} />
                    <span className={cl("message-time-label")}>Local</span>
                    <span>{time}</span>
                </button>
            )}
        </Tooltip>
    );
}

function MemberListLocalTime({ userId }: { userId: string; }) {
    useClockTick();
    const entry = useUserTimeZoneEntry(userId);
    const time = entry && getTimeForEntry(entry);
    const details = entry && getDetailsForEntry(entry);

    if (!time || !details) return null;

    return (
        <Tooltip text={`Current local time: ${time} · ${details}`}>
            {tooltipProps => (
                <button
                    {...tooltipProps}
                    type="button"
                    aria-label={`Current local time ${time}`}
                    className={cl("member-time")}
                    onClick={event => {
                        event.stopPropagation();
                        openEditor(userId);
                    }}
                >
                    <ClockIcon size={11} />
                    <span>{time}</span>
                </button>
            )}
        </Tooltip>
    );
}

export default definePlugin({
    name: "UserTimeZones",
    description: "Shows each configured user's current local time beside messages, in member lists, and on profiles.",
    authors: [{ name: "jhein", id: 0n }],
    dependencies: ["MemberListDecoratorsAPI", "MessageDecorationsAPI"],
    settings,
    patches: [
        {
            find: ".SIDEBAR}),nicknameIcons",
            replacement: {
                match: /#{intl::USER_PROFILE_MEMBER_SINCE}\),.{0,100}userId:(\i\.id)}\)}\)/,
                replace: "$&,$self.TimeZoneSection({userId:$1,isSidebar:true})"
            }
        },
        {
            find: ",applicationRoleConnection:",
            replacement: {
                match: /#{intl::USER_PROFILE_MEMBER_SINCE}\),.{0,100}userId:(\i\.id),.{0,100}}\)}\),/,
                replace: "$&,$self.TimeZoneSection({userId:$1,isSidebar:false}),"
            }
        },
        {
            find: ".MODAL_V2,onClose:",
            replacement: {
                match: /#{intl::USER_PROFILE_MEMBER_SINCE}\),.{0,100}userId:(\i\.id),.{0,100}}\)}\),/,
                replace: "$&,$self.TimeZoneSection({userId:$1,isSidebar:false}),"
            }
        }
    ],
    renderMessageDecoration: ({ message }) => message?.author
        ? <MessageLocalTime userId={message.author.id} />
        : null,
    renderMemberListDecorator: ({ user }) => user
        ? <MemberListLocalTime userId={user.id} />
        : null,
    TimeZoneSection,
});
