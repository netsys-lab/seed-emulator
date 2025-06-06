-- stk_config.sql

CREATE TABLE IF NOT EXISTS v1_stk_config_stats
(
    host_id INTEGER UNSIGNED NOT NULL PRIMARY KEY, -- Unique host id in STKHost of each connection session for a STKPeer
    ip INTEGER UNSIGNED NOT NULL, -- IP decimal of host
    ipv6 TEXT NOT NULL DEFAULT '', -- IPv6 (if exists) in string of host (only created if IPv6 server)
    port INTEGER UNSIGNED NOT NULL, -- Port of host
    online_id INTEGER UNSIGNED NOT NULL, -- Online if of the host (0 for offline account)
    username TEXT NOT NULL, -- First player name in the host (if the host has splitscreen player)
    player_num INTEGER UNSIGNED NOT NULL, -- Number of player(s) from the host, more than 1 if it has splitscreen player
    country_code TEXT NULL DEFAULT NULL, -- 2-letter country code of the host
    version TEXT NOT NULL, -- SuperTuxKart version of the host
    os TEXT NOT NULL, -- Operating system of the host
    connected_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Time when connected
    disconnected_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Time when disconnected (saved when disconnected)
    ping INTEGER UNSIGNED NOT NULL DEFAULT 0 -- Ping of the host
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS v1_countries
(
    country_code TEXT NOT NULL PRIMARY KEY UNIQUE, -- Unique 2-letter country code
    country_flag TEXT NOT NULL, -- Unicode country flag representation of 2-letter country code
    country_name TEXT NOT NULL -- Readable name of this country
) WITHOUT ROWID;

CREATE TABLE ip_ban
(
    ip_start INTEGER UNSIGNED NOT NULL UNIQUE, -- Starting of ip decimal for banning (inclusive)
    ip_end INTEGER UNSIGNED NOT NULL UNIQUE, -- Ending of ip decimal for banning (inclusive)
    starting_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Starting time of this banning entry to be effective
    expired_days REAL NULL DEFAULT NULL, -- Days for this banning to be expired, use NULL for a permanent ban
    reason TEXT NOT NULL DEFAULT '', -- Banned reason shown in user stk menu, can be empty
    description TEXT NOT NULL DEFAULT '', -- Private description for server admin
    trigger_count INTEGER UNSIGNED NOT NULL DEFAULT 0, -- Number of banning triggered by this ban entry
    last_trigger TIMESTAMP NULL DEFAULT NULL -- Latest time this banning entry was triggered
);

CREATE TABLE ipv6_ban
(
    ipv6_cidr TEXT NOT NULL UNIQUE, -- IPv6 CIDR range for banning (for example 2001::/64), use /128 for a specific ip
    starting_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Starting time of this banning entry to be effective
    expired_days REAL NULL DEFAULT NULL, -- Days for this banning to be expired, use NULL for a permanent ban
    reason TEXT NOT NULL DEFAULT '', -- Banned reason shown in user stk menu, can be empty
    description TEXT NOT NULL DEFAULT '', -- Private description for server admin
    trigger_count INTEGER UNSIGNED NOT NULL DEFAULT 0, -- Number of banning triggered by this ban entry
    last_trigger TIMESTAMP NULL DEFAULT NULL -- Latest time this banning entry was triggered
);

CREATE TABLE online_id_ban
(
    online_id INTEGER UNSIGNED NOT NULL UNIQUE, -- Online id from STK addons database for banning
    starting_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Starting time of this banning entry to be effective
    expired_days REAL NULL DEFAULT NULL, -- Days for this banning to be expired, use NULL for a permanent ban
    reason TEXT NOT NULL DEFAULT '', -- Banned reason shown in user stk menu, can be empty
    description TEXT NOT NULL DEFAULT '', -- Private description for server admin
    trigger_count INTEGER UNSIGNED NOT NULL DEFAULT 0, -- Number of banning triggered by this ban entry
    last_trigger TIMESTAMP NULL DEFAULT NULL -- Latest time this banning entry was triggered
);

CREATE TABLE player_reports
(
    server_uid TEXT NOT NULL, -- Report from which server unique id (config filename)
    reporter_ip INTEGER UNSIGNED NOT NULL, -- IP decimal of player who reports
    reporter_ipv6 TEXT NOT NULL DEFAULT '', -- IPv6 (if exists) in string of player who reports (only needed for IPv6 server)
    reporter_online_id INTEGER UNSIGNED NOT NULL, -- Online id of player who reports, 0 for offline player
    reporter_username TEXT NOT NULL, -- Player name who reports
    reported_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Time of reporting
    info TEXT NOT NULL, -- Report info by reporter
    reporting_ip INTEGER UNSIGNED NOT NULL, -- IP decimal of player being reported
    reporting_ipv6 TEXT NOT NULL DEFAULT '', -- IPv6 (if exists) in string of player who reports (only needed for IPv6 server)
    reporting_online_id INTEGER UNSIGNED NOT NULL, -- Online id of player being reported, 0 for offline player
    reporting_username TEXT NOT NULL -- Player name being reported
);

CREATE TABLE ip_mapping
(
    ip_start INTEGER UNSIGNED NOT NULL PRIMARY KEY UNIQUE, -- IP decimal start
    ip_end INTEGER UNSIGNED NOT NULL UNIQUE, -- IP decimal end
    latitude REAL NOT NULL, -- Latitude of this IP range
    longitude REAL NOT NULL, -- Longitude of this IP range
    country_code TEXT NOT NULL -- 2-letter country code
) WITHOUT ROWID;

CREATE TABLE ipv6_mapping
(
    ip_start INTEGER UNSIGNED NOT NULL PRIMARY KEY UNIQUE, -- IP decimal (upper 64bit) start
    ip_end INTEGER UNSIGNED NOT NULL UNIQUE, -- IP decimal (upper 64bit) end
    latitude REAL NOT NULL, -- Latitude of this IP range
    longitude REAL NOT NULL, -- Longitude of this IP range
    country_code TEXT NOT NULL -- 2-letter country code
);