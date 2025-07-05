# Discord Music & Moderation Bot - Simple User Guide

Welcome to your all-in-one Discord Music & Moderation Bot! This guide will help you (yes, even you, cave brain) get the bot running and use all its features, step by step.

---

## 1. Setup (How to Make the Bot Work)

### What you need:
- Python 3.9+
- A Discord bot token (from the Discord Developer Portal)
- ffmpeg (download from https://ffmpeg.org/download.html)
- These Python packages: `discord.py`, `yt-dlp`, `pynacl`, `ffmpeg`

### How to install the requirements:
Open a terminal (win+r then type cmd) and run:
```
pip install discord.py yt-dlp pynacl ffmpeg
```

### How to get ffmpeg:
- Download the static build for your OS from https://ffmpeg.org/download.html
- Unzip it somewhere (e.g., `C:/Bot/ffmpeg/bin/ffmpeg.exe`)

### How to set up your bot token:
- Go to https://discord.com/developers/applications
- Create a new application, add a bot, and copy the token
- Set it as an environment variable named `BOT_TOKEN` **or** edit the code and replace `YOUR_BOT_TOKEN_HERE` with your token (not recommended for public code)

### How to run the bot:
```
python Bot.py
```

---

## 2. Configuration (Optional)
You can change where your music is stored, ffmpeg path, etc. by setting these environment variables:
- `BOT_MUSIC_DIR` (default: `C:/Music`)
- `BOT_YT_DL_SUBDIR` (default: `Audio`)
- `BOT_PLAYLIST_SUBDIR` (default: `Playlists`)
- `BOT_FFMPEG_PATH` (default: `C:/Bot/ffmpeg/bin/ffmpeg.exe`)
- `BOT_PREFIX` (default: `!`)

Example (Windows PowerShell):
```
$env:BOT_TOKEN="your_token_here"
python BeaBot.py
```

---

## 3. Using the Bot (Commands)

### For Everyone (Community Commands)
Type these as slash commands in Discord (start with `/`):

- `/help` — Show all community commands
- `/join` — Bot joins your voice channel
- `/leave` — Bot leaves the voice channel
- `/play <keyword>` — Play a song by keyword
- `/yt <query>` — Download and play a YouTube song
- `/ytplaylist <playlist_url>` — Download and queue all songs from a YouTube playlist
- `/pause` — Pause playback
- `/resume` — Resume playback
- `/stop` — Stop playback and clear queue
- `/skip` — Skip current song
- `/skipto <index>` — Skip to a specific song in the queue
- `/loop <off|one|all>` — Set repeat mode
- `/listsongs` — List all songs
- `/listbyartist` — List songs by artist
- `/listbyletter <letter>` — List songs by first letter
- `/listbyname <name>` — List songs by name
- `/listbyfolder <folder>` — List songs in a folder
- `/stoplist` — Stop the current song list
- `/nowplaying` — Show the current song
- `/queue` — Show the current queue
- `/history` — Show playback history
- `/random20` — Queue 20 random songs
- `/loadplaylist` — Load a playlist
- `/listplaylists` — List all playlists
- `/saveplaylist <name>` — Save the current queue as a playlist

### For Moderators (Admin Only)
- `/modhelp` — Show all moderator commands
- `/addword <word>` — Add a word to the filter
- `/removeword <word>` — Remove a word from the filter
- `/listwords` — List all filtered words
- `/kick <user> [reason]` — Kick a user
- `/ban <user> [reason]` — Ban a user
- `/tempban <user> <duration> [reason]` — Temporarily ban a user
- `/tempkick <user> <duration> [reason]` — Temporarily kick a user
- `/announce <...>` — Send an announcement to a channel
- `/deleteplaylist` — Delete a playlist

---

## 4. Troubleshooting
- If the bot doesn't join voice, make sure it has permission and you are in a voice channel.
- If music doesn't play, check your ffmpeg path and that your files are in the right folder.
- If you get errors about missing packages, run the pip install command again.
- If you get permission errors, make sure your bot has the right Discord permissions (Manage Messages, Connect, Speak, etc).

---

## 5. Safety & Security
- Never share your bot token with anyone!
- Use environment variables for secrets if possible.
- This bot is a template: you can add, remove, or change features as you wish.

---

## 6. Need More Help?
- Read the comments in the code.
- Google the error message you see.
- Ask a friend or search Discord.py/yt-dlp documentation.

---

Enjoy the bot - NamelessPyro