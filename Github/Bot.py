"""
BeaBot: Discord Music & Moderation Bot
=====================================

A public-ready Discord bot combining music playback (with YouTube/playlist support) and moderation features (word filter, kick/ban, announcements, etc.).

Instructions:
- Install requirements: discord.py, yt-dlp, pynacl, ffmpeg.
- Place your bot token in the indicated section below.
- Set your music directory and other paths as needed.
- Run with: python BeaBot.py

(c) 2025, Public Release. No sensitive information included.
"""

import os
import sys
import io
import re
import json
import signal
import random
import logging
import asyncio
import contextlib
import datetime
from typing import List, Optional, Tuple

import discord
from discord.ext import commands, tasks
from discord import app_commands


# === CONFIGURATION ===
# Template: set your music and ffmpeg paths here, or use environment variables.
MUSIC_DIR = os.environ.get("BOT_MUSIC_DIR", "C:/Music")
YT_DOWNLOAD_DIR = os.path.join(MUSIC_DIR, os.environ.get("BOT_YT_DL_SUBDIR", "Audio"))
PLAYLIST_DIR = os.path.join(MUSIC_DIR, os.environ.get("BOT_PLAYLIST_SUBDIR", "Playlists"))
FFMPEG_PATH = os.environ.get("BOT_FFMPEG_PATH", "C:/Bot/ffmpeg/bin/ffmpeg.exe")
FILTER_FILE = os.environ.get("BOT_FILTER_FILE", "filtered_words.json")

os.makedirs(YT_DOWNLOAD_DIR, exist_ok=True)
os.makedirs(PLAYLIST_DIR, exist_ok=True)

# === LOGGING SETUP ===
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# === BOT TOKEN (INSERT YOUR TOKEN BELOW) ===
BOT_TOKEN = os.environ.get("YOUR_BOT_TOKEN_HERE")  # Set as env var or replace string

# === INTENTS ===
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=os.environ.get("BOT_PREFIX", "!"), intents=intents)
tree = bot.tree
# === INTENTS ===
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=os.environ.get("BOT_PREFIX", "!"), intents=intents)
tree = bot.tree

# === MUSIC BOT STATE ===
MAX_QUEUE_LENGTH = 100
queues = {}
active_views = {}
history = {}
repeat_mode = {}  # guild_id: 'off' | 'one' | 'all'

# === MODERATION STATE ===
temp_actions = {}
if os.path.exists(FILTER_FILE):
    with open(FILTER_FILE, "r") as f:
        FILTERED_WORDS = set(json.load(f))
else:
    FILTERED_WORDS = set()

def save_filtered_words():
    with open(FILTER_FILE, "w") as f:
        json.dump(sorted(list(FILTERED_WORDS)), f, indent=2)

def contains_filtered_word(content: str):
    for word in FILTERED_WORDS:
        if re.search(rf'\\b{re.escape(word)}\\b', content, re.IGNORECASE):
            return True
    return False

# === UTILITY FUNCTIONS ===
def find_mp3_files() -> List[str]:
    mp3_files = []
    for root, _, files in os.walk(MUSIC_DIR):
        for file in files:
            if file.lower().endswith(".mp3"):
                mp3_files.append(os.path.join(root, file))
    return mp3_files

def search_mp3(keyword: str) -> Optional[str]:
    keyword = keyword.lower()
    for root, _, files in os.walk(MUSIC_DIR):
        for file in files:
            if file.lower().endswith(".mp3") and keyword in file.lower():
                return os.path.join(root, file)
    return None

async def download_youtube_mp3(query: str) -> Tuple[Optional[str], Optional[str]]:
    import yt_dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'outtmpl': os.path.join(YT_DOWNLOAD_DIR, '%(title)s_%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=True)
                if 'entries' in info:
                    info = info['entries'][0]
                filename = ydl.prepare_filename(info)
                filename = os.path.splitext(filename)[0] + '.mp3'
                return filename, info.get('title', None)
    except Exception as e:
        logging.error(f"YT ERROR: {e}")
        return None, None

# === EMBED/VIEW CLASSES ===
class PagedEmbedView(discord.ui.View):
    def __init__(self, entries: List[str], title: str = "", color: discord.Color = discord.Color.blue(), chunk_size: int = 10, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.entries = entries
        self.chunk_size = chunk_size
        self.page = 0
        self.title = title
        self.color = color

    def get_embed(self) -> discord.Embed:
        start = self.page * self.chunk_size
        end = start + self.chunk_size
        lines = self.entries[start:end]
        numbered = [f"{i+1}. {line}" for i, line in enumerate(lines, start=start)]
        return discord.Embed(
            title=self.title,
            description="\n".join(numbered) if numbered else "No entries.",
            color=self.color
        )

    async def update(self, interaction: discord.Interaction):
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await self.update(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (self.page + 1) * self.chunk_size < len(self.entries):
            self.page += 1
        await self.update(interaction)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass

class PlaylistSelect(discord.ui.Select):
    def __init__(self, playlists: List[str], placeholder: str, callback):
        options = [discord.SelectOption(label=p) for p in playlists]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self.callback_fn = callback

    async def callback(self, interaction: discord.Interaction):
        await self.callback_fn(interaction, self.values[0])

class PlaylistSelectView(discord.ui.View):
    def __init__(self, playlists: List[str], placeholder: str, callback):
        super().__init__(timeout=60)
        self.add_item(PlaylistSelect(playlists, placeholder, callback))

# === MODERATION UTILS ===
def create_embed(title: str, description: str, color=discord.Color.red()):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Moderation Bot")
    embed.timestamp = datetime.datetime.now(datetime.UTC)
    return embed

async def log_to_modlog(guild: discord.Guild, embed: discord.Embed):
    log_channel = discord.utils.get(guild.text_channels, name="mod-log")
    if log_channel:
        await log_channel.send(embed=embed)

# === EVENTS ===
@bot.event
def on_message(message):
    if message.author.bot:
        return
    if contains_filtered_word(message.content):
        asyncio.create_task(message.delete())
        embed = create_embed("Filtered Language", f"{message.author.mention}, please avoid using inappropriate language.")
        asyncio.create_task(message.channel.send(embed=embed, delete_after=5))
    asyncio.create_task(bot.process_commands(message))

@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            await tree.sync(guild=guild)
            print(f"Synchronized slash commands in: {guild.name} ({guild.id})")
        except Exception as e:
            print(f"Failed to sync commands in {guild.name} ({guild.id}): {e}")
    try:
        await tree.sync()
        print("Globally synchronized slash commands.")
    except Exception as e:
        print(f"Global sync failed: {e}")
    if not unban_task.is_running():
        unban_task.start()
    print(f"Bot is ready as {bot.user}")
    bot.loop.create_task(auto_disconnect_task())

# === ERROR HANDLER ===
@tree.error
def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        asyncio.create_task(interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True))
    else:
        asyncio.create_task(interaction.response.send_message("⚠️ An unexpected error occurred.", ephemeral=True))
        raise error

# === MODERATION COMMANDS ===
@tree.command(name="addword", description="Add a word to the filter")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(word="The word to block")
async def addword(interaction: discord.Interaction, word: str):
    word = word.lower()
    if word in FILTERED_WORDS:
        await interaction.response.send_message(f"The word '{word}' is already filtered.")
    else:
        FILTERED_WORDS.add(word)
        save_filtered_words()
        await interaction.response.send_message(f"Added '{word}' to the word filter.")

@tree.command(name="removeword", description="Remove a word from the filter")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(word="The word to remove")
async def removeword(interaction: discord.Interaction, word: str):
    word = word.lower()
    if word not in FILTERED_WORDS:
        await interaction.response.send_message(f"The word '{word}' is not in the filter.")
    else:
        FILTERED_WORDS.remove(word)
        save_filtered_words()
        await interaction.response.send_message(f"Removed '{word}' from the filter.")

@tree.command(name="listwords", description="List all filtered words")
@app_commands.checks.has_permissions(administrator=True)
async def listwords(interaction: discord.Interaction):
    if not FILTERED_WORDS:
        await interaction.response.send_message("No words are currently being filtered.")
    else:
        word_list = "\n".join(sorted(FILTERED_WORDS))
        await interaction.response.send_message(f"**Filtered words:**\n```\n{word_list}\n```")

@tree.command(name="kick", description="Kick a user")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="User to kick", reason="Reason for kicking")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    await user.kick(reason=reason)
    embed = create_embed("User Kicked", f"User: {user.mention}\nReason: {reason}")
    await interaction.response.send_message(embed=embed)
    await log_to_modlog(interaction.guild, embed)

@tree.command(name="ban", description="Ban a user")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="User to ban", reason="Reason for banning")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    await user.ban(reason=reason)
    embed = create_embed("User Banned", f"User: {user.mention}\nReason: {reason}")
    await interaction.response.send_message(embed=embed)
    await log_to_modlog(interaction.guild, embed)

@tree.command(name="tempban", description="Temporarily ban a user")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="User to ban", duration="Time in seconds", reason="Reason")
async def tempban(interaction: discord.Interaction, user: discord.Member, duration: int, reason: str = "No reason provided"):
    await user.ban(reason=reason)
    until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=duration)
    temp_actions[user.id] = ("ban", until)
    embed = create_embed("Temporary Ban", f"User: {user.mention}\nDuration: {duration} seconds\nReason: {reason}")
    await interaction.response.send_message(embed=embed)
    await log_to_modlog(interaction.guild, embed)

@tree.command(name="tempkick", description="Temporarily kick a user")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="User to kick", duration="Time in seconds", reason="Reason")
async def tempkick(interaction: discord.Interaction, user: discord.Member, duration: int, reason: str = "No reason provided"):
    await user.kick(reason=reason)
    embed = create_embed("Temporary Kick", f"User: {user.mention}\nDuration: {duration} seconds\nReason: {reason}")
    await interaction.response.send_message(embed=embed)
    await log_to_modlog(interaction.guild, embed)

@tree.command(name="announce", description="Send an announcement")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    use_embed="Send as embed?",
    title="Embed title",
    description="Embed description",
    message="Plain text message (ignored if embed is used)",
    channel="Channel to send the announcement to",
    author="Author name (for embed)",
    footer="Footer text (for embed)",
    color="Hex color code (e.g. #FF0000)"
)
async def announce(
    interaction: discord.Interaction,
    use_embed: bool,
    channel: discord.TextChannel,
    title: Optional[str] = None,
    description: Optional[str] = None,
    message: Optional[str] = None,
    author: Optional[str] = None,
    footer: Optional[str] = None,
    color: Optional[str] = None
):
    await interaction.response.defer(thinking=True)
    if not use_embed and not message:
        await interaction.followup.send("Please provide a message if you're not using an embed.")
        return
    if use_embed:
        embed_color = discord.Color.default()
        if color:
            try:
                embed_color = discord.Color(int(color.replace("#", ""), 16))
            except ValueError:
                await interaction.followup.send("Invalid hex color. Use format like `#FF0000`.")
                return
        embed = discord.Embed(title=title or "Announcement", description=description or "", color=embed_color)
        if author:
            embed.set_author(name=author)
        if footer:
            embed.set_footer(text=footer)
        embed.timestamp = datetime.datetime.now(datetime.UTC)
        await channel.send(embed=embed)
        await interaction.followup.send(f"Embed announcement sent to {channel.mention}")
    else:
        await channel.send(message)
        await interaction.followup.send(f"Message sent to {channel.mention}")


# === COMMUNITY HELP COMMAND ===
@tree.command(name="help", description="Show all available community commands and their usage.")
async def help_command(interaction: discord.Interaction):
    """Show all available community commands and their usage."""
    help_text = (
        "**Community Commands:**\n"
        "/help - Show this help message\n"
        "/join - Join your voice channel\n"
        "/leave - Leave the voice channel\n"
        "/play <keyword> - Play a song by keyword\n"
        "/yt <query> - Download and play a YouTube song\n"
        "/ytplaylist <playlist_url> - Download and queue all songs from a YouTube playlist\n"
        "/pause - Pause playback\n"
        "/resume - Resume playback\n"
        "/stop - Stop playback and clear queue\n"
        "/skip - Skip current song\n"
        "/skipto <index> - Skip to a specific song in the queue\n"
        "/loop <off|one|all> - Set repeat mode: off, repeat song, or repeat queue\n"
        "/listsongs - List all songs\n"
        "/listbyartist - List songs by artist\n"
        "/listbyletter <letter> - List songs by first letter\n"
        "/listbyname <name> - List songs by name\n"
        "/listbyfolder <folder> - List songs in a folder\n"
        "/stoplist - Stop the current song list\n"
        "/nowplaying - Show the current song\n"
        "/queue - Show the current queue\n"
        "/history - Show playback history\n"
        "/random20 - Queue 20 random songs\n"
        "/loadplaylist - Load a playlist\n"
        "/listplaylists - List all playlists\n"
        "/saveplaylist <name> - Save the current queue as a playlist\n"
    )
    await interaction.response.send_message(help_text, ephemeral=True)

# === MODERATOR HELP COMMAND ===
@tree.command(name="modhelp", description="Show all moderator-only commands and their usage.")
@app_commands.checks.has_permissions(administrator=True)
async def modhelp_command(interaction: discord.Interaction):
    """Show all moderator-only commands and their usage."""
    help_text = (
        "**Moderator Commands:**\n"
        "/modhelp - Show this help message (moderators only)\n"
        "/addword <word> - Add a word to the filter\n"
        "/removeword <word> - Remove a word from the filter\n"
        "/listwords - List all filtered words\n"
        "/kick <user> [reason] - Kick a user\n"
        "/ban <user> [reason] - Ban a user\n"
        "/tempban <user> <duration> [reason] - Temporarily ban a user\n"
        "/tempkick <user> <duration> [reason] - Temporarily kick a user\n"
        "/announce <...> - Send an announcement to a channel\n"
        "/deleteplaylist - Delete a playlist\n"
    )
    await interaction.response.send_message(help_text, ephemeral=True)

# === BACKGROUND TASKS ===
@tasks.loop(seconds=10)
async def unban_task():
    now = datetime.datetime.now(datetime.UTC)
    for user_id, (action, end_time) in list(temp_actions.items()):
        if now >= end_time:
            for guild in bot.guilds:
                try:
                    user = await bot.fetch_user(user_id)
                    await guild.unban(user)
                    print(f"Unbanned {user} in {guild.name}")
                except discord.NotFound:
                    continue
            temp_actions.pop(user_id)

async def auto_disconnect_task():
    await bot.wait_until_ready()
    disconnecting_guilds = set()
    while not bot.is_closed():
        for guild in bot.guilds:
            vc = guild.voice_client
            if vc and not vc.is_playing() and not vc.is_paused():
                await vc.disconnect()
        await asyncio.sleep(30)

# === SHUTDOWN HANDLER ===
def shutdown_handler(*_):
    logging.info("Received shutdown signal. Disconnecting bot...")
    for guild in bot.guilds:
        vc = guild.voice_client
        if vc:
            asyncio.create_task(vc.disconnect())
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# === MAIN ===
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
