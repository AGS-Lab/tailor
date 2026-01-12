# Prompt Refiner Plugin

A Tailor plugin that refines and improves your prompts before sending them to the LLM for better responses.

## Features

- ✨ **One-Click Refinement**: Adds a sparkle button to your vault toolbar
- 🎯 **Smart Improvement**: Uses AI to make your prompts clearer, more specific, and better structured
- ⚡ **Non-Destructive**: Shows the refined prompt for review before sending
- 🛡️ **Guardrails**: Validates input before processing

## Installation

### Via Plugin Store (Recommended)
1. Open your vault in Tailor
2. Go to Plugin Store
3. Search for "Prompt Refiner"
4. Click Install

### Manual Installation
1. Download or clone this repository
2. Copy the folder to your vault's `plugins` directory:
   ```
   your-vault/
   └── plugins/
       └── prompt-refiner/
           ├── main.py
           ├── plugin.json
           └── settings.json
   ```
3. Enable the plugin in Vault Settings → Plugins

## Usage

1. Type your rough prompt in the chat input
2. Click the ✨ sparkle button in the toolbar
3. Wait for the AI to refine your prompt
4. Review the refined prompt in the input field
5. Press Send to chat with the improved prompt

## Example

**Before:**
> explain python decorators

**After:**
> Explain Python decorators with the following: 1) What they are and their purpose, 2) How the @ syntax works, 3) A simple example with code, 4) Common use cases like @property and @staticmethod.

## Configuration

The plugin uses your vault's configured LLM (OpenAI API). Make sure you have:
1. An OpenAI API key set in your `.env` file
2. The LLM plugin enabled

## Requirements

- Tailor v1.0.0 or higher
- OpenAI API key configured

## License

MIT License - feel free to use and modify!

## Contributing

Issues and pull requests welcome at [GitHub](https://github.com/tailor-dev/prompt-refiner).
