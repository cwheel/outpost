# 🏕️ 🚐 Outpost

Near real time GPS synchronization from remote Victron (VenusOS) systems to PostGIS databases for future analysis. Perfect for plotting your off-grid van adventures.

## Overview

Outpost provides highly efficient transmission of GPS data from remote installations to a PostgreSQL database equipped with PostGIS. It's designed specifically for cellular and satellite networks where bandwidth is limited or expensive, and optimization is critical.

## Protocol

The Outpost protocol uses a custom binary format over CoAP to minimize bandwith use. Highlights include:

- **Delta compression**: Position samples are encoded as deltas from a reference point
- **Batch transmission**: Multiple GPS positions are batched together for efficient transport (up to 40 at a time)
- **AES-256-GCM encryption**: Secure transmission with pre-shared keys instead of heavy weight TLS

GPS positions are transmited using only **_9 bytes_** per sample (with a 16 byte header per payload). Outpost prioritizes small message size over all else, and thus does _not_ include any kind of system/device identifier. This is trivial to add (and would only require one additional byte per payload), but alas I only have one Victron install/van.

Given the limited range of values representable using only 9 bytes and the diffirent values each position sample encodes, each sample is of limited but acceptable precision:

- Payload header coordinates to 0.0000001
- Cooordinate deltas to 0.0001 or roughly ~10 meters (depending where in the world you are)
- Altitudes in whole meters
- Speeds to 0.1 kilometers per hour

## Installation

### Server Setup

1. **Generate key:**
   ```bash
   ./tools/generate_key.sh outpost.psk
   ```
   
2. **Deploy with Docker Compose:**
   ```bash
   export OUTPOST_PSK=outpost.psk
   docker-compose up -d
   ```

   This starts:
   - Outpost server on port 5683/udp
   - PostgreSQL with PostGIS on port 5432 (local host access only)

   Server logs can be found in `.logs/`.

### Client Setup (VenusOS)

1. **Copy PSK file** to the Victron system

2. **Install client:**
   ```bash
   ./tools/install.sh --psk-file <your-psk>.psk --host your-server.com --device /dev/ttyUSB0 --baud 38400
   ```

      _Note: The installer requires `pip3` be installed. This is not included in the default Venus image. See [here](https://github.com/victronenergy/venus/wiki/commandline---development#opkg) for details on using `opkg` to install pip._

   The path to your GPS device is highly dependent on your exact system configuration, as is the baud rate. VenusOS only supports GPS devices with a baud of 4800 or 38400, so your device is _likely_ using one of those.

3. **Verify installation:**
   ```bash
   /etc/init.d/outpost-client status
   tail -f /var/log/outpost-client.log
   ```

### Client Updates

To update an existing client installation, simply re-run the install script (the parameters used last time need not be added again).

## GPS Samples

GPS data is stored in the `positions` table with PostGIS geometry columns. The client automatically handles:
- GPS parsing (NMEA format)
- Position filtering (duplicate detection)
- Network connectivity monitoring
- Automatic reconnection
