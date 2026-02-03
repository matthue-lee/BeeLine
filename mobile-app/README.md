# BeeLine Viewer (Expo)

Quick Expo/React Native client to inspect releases from the BeeLine ingestion database.

## Prerequisites

- Node.js 18+
- `npm install --global expo-cli` (optional, `npx expo` also works)
- Python Flask app serving `/releases` (run `FLASK_APP=beeline_ingestor.app flask run`)

## Setup

```bash
cd mobile-app
npm install
```

Override the backend URL if you are testing on a device by setting `EXPO_PUBLIC_API_BASE_URL`:

```bash
EXPO_PUBLIC_API_BASE_URL="http://192.168.1.23:5000" npx expo start
```

Otherwise it defaults to `http://localhost:5000` for simulators.

## Running

```bash
npm run start      # opens the Expo dev menu
npm run ios        # launch iOS simulator
npm run android    # launch Android emulator
```

Pull to refresh to fetch the latest releases. Tap a card to read the full cleaned text.
