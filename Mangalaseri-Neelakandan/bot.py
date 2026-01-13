from threading import Thread
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()



import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 🔔 Announcement Channel ID (Locked)
ANNOUNCE_CHANNEL_ID = 1457025024669126747

# Setup Intents
intents = discord.Intents.default()
intents.message_content = False  # not needed for slash commands

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- MOCK EVENTS ----------------
# Time format used internally: YYYY-MM-DD HH:MM (24 hour)
EVENTS = [
    {
        "title": "AI Workshop",
        "start": "2026-01-14 15:00",
        "end": "2026-01-14 16:30",
        "location": "Seminar Hall, D Block"
    },
    {
        "title": "Web Development Introduction",
        "start": "2026-01-19 13:00",
        "end": "2026-01-19 14:00",
        "location": "SDPK Hall, A Block"
    }
]

# Load announced events from file (Persistence)
def load_announced():
    if os.path.exists("announced.json"):
        with open("announced.json", "r") as f:
            data = json.load(f)
            return set(data.get("soon", [])), set(data.get("live", []))
    return set(), set()

# Save announced events to file
def save_announced(soon, live):
    with open("announced.json", "w") as f:
        json.dump({"soon": list(soon), "live": list(live)}, f)

# To avoid duplicate announcements
announced_soon, announced_live = load_announced()

def parse_time(t):
    return datetime.strptime(t, "%Y-%m-%d %H:%M")


# ---------------- BOT EVENTS ----------------

@bot.event
async def on_ready():
    # Force sync slash commands to your server
    guild = discord.Object(id=1455556204679004173) 
    try:
        # This copies your global commands (the ones you defined) to your specific server
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"🤖 {bot.user} is online and slash commands are synced to guild {guild.id}!")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    
    if not announce_loop.is_running():
        announce_loop.start()


# ---------------- SLASH COMMANDS ----------------

@bot.tree.command(name="events", description="Show all upcoming campus events")
async def events(interaction: discord.Interaction):
    if interaction.channel.id != ANNOUNCE_CHANNEL_ID:
        await interaction.response.send_message("Use this command only in the announcement channel.", ephemeral=True)
        return

    now = datetime.now()
    upcoming = []

    for e in EVENTS:
        start = parse_time(e["start"])
        if start > now:
            upcoming.append(e)

    if not upcoming:
        await interaction.response.send_message("📭 No upcoming events found.")
        return

    msg = "📅 **Upcoming Events:**\n"
    for e in upcoming:
        msg += (
            f"• **{e['title']}**\n"
            f"  🕒 {e['start']}\n"
            f"  📍 {e['location']}\n"
        )

    await interaction.response.send_message(msg)


@bot.tree.command(name="now", description="Show events that are happening right now")
async def now(interaction: discord.Interaction):
    if interaction.channel.id != ANNOUNCE_CHANNEL_ID:
        await interaction.response.send_message("Use this command only in the announcement channel.", ephemeral=True)
        return

    now_time = datetime.now()
    ongoing = []

    for e in EVENTS:
        start = parse_time(e["start"])
        end = parse_time(e["end"])
        if start <= now_time <= end:
            ongoing.append(e)

    if not ongoing:
        await interaction.response.send_message("😴 No events are happening right now.")
        return

    msg = "🔴 **Happening Now:**\n"
    for e in ongoing:
        msg += (
            f"• **{e['title']}**\n"
            f"  📍 {e['location']}\n"
        )

    await interaction.response.send_message(msg)


# --- NEW ANNOUNCE COMMAND (Dyno Style) ---
@bot.tree.command(name="announce", description="Announce a new event (Dyno Style)")
@app_commands.describe(
    title="Event title (e.g., AI Workshop)",
    date="Date (Format: YYYY-MM-DD)",
    start_time="Start time (Format: HH:MM 24hr)",
    end_time="End time (Format: HH:MM 24hr)",
    location="Where is it happening?",
    description="Optional event description",
    ping_everyone="Ping @everyone? (true/false)"
)
async def announce(
    interaction: discord.Interaction,
    title: str,
    date: str,
    start_time: str,
    end_time: str,
    location: str,
    description: str = None,
    ping_everyone: str = "true"
):
    if interaction.channel.id != ANNOUNCE_CHANNEL_ID:
        await interaction.response.send_message(
            "Use this command only in the announcement channel.",
            ephemeral=True
        )
        return

    # 1. Construct the full datetime strings for internal logic
    full_start_str = f"{date} {start_time}"
    full_end_str = f"{date} {end_time}"

    # 2. Validate time format
    try:
        # Check if the text matches YYYY-MM-DD HH:MM
        dt_start = datetime.strptime(full_start_str, "%Y-%m-%d %H:%M")
        dt_end = datetime.strptime(full_end_str, "%Y-%m-%d %H:%M")
        
        # Logic check: End time must be after start time
        if dt_end <= dt_start:
             await interaction.response.send_message(
                "❌ End time cannot be before Start time.", ephemeral=True
            )
             return
             
    except ValueError:
        await interaction.response.send_message(
            "❌ **Invalid format!**\nUse `YYYY-MM-DD` for date and `HH:MM` (24hr) for time.\nExample: `2026-01-20` and `14:30`",
            ephemeral=True
        )
        return

    # 3. Add to EVENTS list so the background loop picks it up
    EVENTS.append({
        "title": title,
        "start": full_start_str,
        "end": full_end_str,
        "location": location
    })

    # 4. Create a Dyno-style Embed
    embed = discord.Embed(
        title=f"📢 {title}",
        description=description or "A new event has been scheduled! Check the details below.",
        color=discord.Color.blue(), 
        timestamp=datetime.now()
    )
    
    embed.add_field(name="📅 Date", value=date, inline=True)
    embed.add_field(name="🕒 Time", value=f"{start_time} - {end_time}", inline=True)
    embed.add_field(name="📍 Location", value=location, inline=False)
    
    # Optional: Footer and Thumbnail
    embed.set_footer(text=f"Posted by {interaction.user.display_name}")
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/747/747310.png")

    # 5. Send the announcement
    await interaction.response.defer()
    
    # Send content (@everyone ping if enabled) + Embed
    mention = "@everyone" if ping_everyone.lower() in ["true", "yes", "1"] else ""
    await interaction.channel.send(content=mention or None, embed=embed)
    
    await interaction.followup.send("✅ Event announced successfully!", ephemeral=True)


# ---------------- AUTO ANNOUNCEMENT LOOP ----------------

@tasks.loop(minutes=1)
async def announce_loop():
    global announced_soon, announced_live
    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    if not channel:
        return

    now = datetime.now()

    for idx, e in enumerate(EVENTS):
        start = parse_time(e["start"])
        end = parse_time(e["end"])
        event_key = f"{idx}-{e['start']}"

        # ⏰ 10 minutes before event
        soon_time = start - timedelta(minutes=10)
        if soon_time <= now < start and event_key not in announced_soon:
            await channel.send(
                f"⏰ **Event starting soon!**\n"
                f"🎯 **{e['title']}**\n"
                f"🕒 {e['start']}\n"
                f"📍 {e['location']}"
            )
            announced_soon.add(event_key)
            save_announced(announced_soon, announced_live)

        # 🔴 When event starts
        if start <= now < end and event_key not in announced_live:
            await channel.send(
                f"🔴 **Event is LIVE now!**\n"
                f"🎯 **{e['title']}**\n"
                f"📍 {e['location']}\n"
                f"Mark your attendance in the app!"
            )
            announced_live.add(event_key)
            save_announced(announced_soon, announced_live)


# ---------------- RUN BOT ----------------
bot.run(TOKEN)