# World of Tanks Chat Translator

A real-time chat translator mod for World of Tanks that automatically translates messages from any language to English using Microsoft Translator API.

## Features

- 🌍 **Automatic Language Detection** - Detects and translates from 60+ languages
- ⚡ **No Performance Impact** - Async translation for battle/training chat
- 💬 **All Chat Types Supported**:
  - Platoon chat
  - Training room chat
  - Battle team chat
  - Battle all chat
- 🎯 **Smart English Detection** - Skips messages already in English
- 💾 **Translation Caching** - Instant translation for repeated messages
- 📊 **Confidence Scores** - Shows language detection confidence
- 🔧 **Debug Logging** - Detailed logs for troubleshooting

## Requirements

- World of Tanks (tested on 2.0.0.0)
- Microsoft Azure Translator API key (free tier available)
- Python 2.7 (for building from source)

## Quick Start (3 Simple Steps)

### Step 1: Get Your Free API Key
1. Go to https://azure.microsoft.com/free/cognitive-services/
2. Click "Try Azure for free" 
3. Create a "Translator" resource (2 million characters free/month!)
4. Copy your API key and region from "Keys and Endpoint"

### Step 2: Set Up This Mod
1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/wot-chat-translator.git
   cd wot-chat-translator
   ```

2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and replace:
   - `YOUR_API_KEY_HERE` → Your actual API key
   - `YOUR_REGION_HERE` → Your region (e.g., `eastus`)

### Step 3: Build & Install
```bash
python build.py
```

Copy `build/ChatTranslator.wotmod` to `World_of_Tanks/mods/<game_version>/`

**That's it!** Launch World of Tanks and foreign messages will be translated automatically.

## Alternative Configuration Methods

### Method 1: Using Environment Variables
Instead of `.env` file, you can set system environment variables:
```bash
# Windows
set MICROSOFT_TRANSLATOR_KEY=your_api_key_here
set MICROSOFT_TRANSLATOR_REGION=your_region_here

# Linux/Mac
export MICROSOFT_TRANSLATOR_KEY=your_api_key_here
export MICROSOFT_TRANSLATOR_REGION=your_region_here
```

### Method 2: Direct Source Edit
Edit `mod_MicrosoftTranslator.py` lines 18-19:
```python
API_KEY = 'your_actual_api_key'
API_REGION = 'your_actual_region'  # e.g., 'eastus'
```

## How It Works

The mod hooks into World of Tanks' messenger system to intercept chat messages before they're displayed. When a non-English message is detected:

1. **Language Detection**: Microsoft Translator API automatically detects the source language
2. **Translation**: Message is translated to English with confidence scoring
3. **Display Format**: `[RO→en] Hello | salut` (shows source language, translation, and original)
4. **Caching**: Translations are cached to avoid repeated API calls

### Technical Details

- **Async Translation**: Battle and training room messages use async translation with 8-second timeout to prevent lag
- **Sync Translation**: Platoon messages use synchronous translation for reliability
- **Smart Detection**: Common English words and gaming phrases are detected to skip unnecessary translations
- **API Efficiency**: Messages with >85% English confidence are skipped

## Troubleshooting

### Check Logs
Debug logs are saved to `microsoft_translator.log` in your World of Tanks folder.

### Common Issues

**401 Unauthorized Error**
- Check your API key is correct
- Verify the region matches your Azure resource
- Ensure your Azure subscription is active

**Messages Not Translating**
- Check if messages are already in English (85% confidence threshold)
- Verify API credentials are set correctly
- Check logs for specific errors

**Lag During Translation**
- This is normal for the first translation (API call)
- Subsequent identical messages use cache (instant)
- Battle chat uses async to minimize impact

## Development

### Project Structure
```
wot-chat-translator/
├── mod_MicrosoftTranslator.py  # Main translator mod
├── build.py                     # Build script
├── .env.example                 # Environment variables template
├── README.md                    # This file
└── build/                       # Generated .wotmod files
```

### Building for Distribution

1. Set environment variables or edit the source
2. Run `python build.py`
3. The `.wotmod` file will be created in `build/`

### Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License

MIT License - See [LICENSE](LICENSE) file for details

## Disclaimer

This mod is not affiliated with or endorsed by Wargaming.net. Use at your own risk.

## Support

- Report issues: [GitHub Issues](../../issues)
- Discord: [Join our Discord](#) (optional)

## Credits

- Microsoft Translator API for translation services
- World of Tanks modding community for documentation
- Contributors and testers

---

**Note**: Keep your API keys secure! Never commit them to public repositories.