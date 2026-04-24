import os
import time
import random
import sqlite3
import asyncio
from datetime import datetime
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# =========================================================
# AYARLAR
# =========================================================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN bulunamadı. .env dosyasını kontrol et.")

GUILD_ID = 1496515150553944096
OWNER_USER_ID = 1365752307056119982
CO_OWNER_USER_ID = 1129879855492780153

DB_FILE = "zental.db"
XP_COOLDOWN_SECONDS = 60

# =========================================================
# OYUNLAR
# =========================================================
GAMES = [
    {
        "role": "🎮 GTA V",
        "category": "🎮 GTA V",
        "slug": "gta-v",
        "display": "GTA V",
        "aliases": ["Grand Theft Auto V", "Grand Theft Auto 5", "GTA V", "GTA 5"],
    },
    {
        "role": "⚔️ LoL",
        "category": "🎮 League of Legends",
        "slug": "lol",
        "display": "League of Legends",
        "aliases": ["League of Legends", "LoL"],
    },
    {
        "role": "🎯 VALORANT",
        "category": "🎮 VALORANT",
        "slug": "valorant",
        "display": "VALORANT",
        "aliases": ["VALORANT"],
    },
    {
        "role": "🔫 CS2",
        "category": "🎮 Counter-Strike 2",
        "slug": "cs2",
        "display": "Counter-Strike 2",
        "aliases": ["Counter-Strike 2", "Counter Strike 2", "CS2"],
    },
    {
        "role": "🧱 Minecraft",
        "category": "🎮 Minecraft",
        "slug": "minecraft",
        "display": "Minecraft",
        "aliases": ["Minecraft"],
    },
    {
        "role": "☢️ Rust",
        "category": "🎮 Rust",
        "slug": "rust",
        "display": "Rust",
        "aliases": ["Rust"],
    },
    {
        "role": "🐔 PUBG",
        "category": "🎮 PUBG",
        "slug": "pubg",
        "display": "PUBG",
        "aliases": ["PUBG", "PUBG: BATTLEGROUNDS", "PLAYERUNKNOWN'S BATTLEGROUNDS"],
    },
    {
        "role": "📱 PUBG Mobile",
        "category": "🎮 PUBG Mobile",
        "slug": "pubg-mobile",
        "display": "PUBG Mobile",
        "aliases": ["PUBG Mobile", "PUBG MOBILE"],
    },
    {
        "role": "👨‍🚀 Among Us",
        "category": "🎮 Among Us",
        "slug": "among-us",
        "display": "Among Us",
        "aliases": ["Among Us"],
    },
    {
    "role": "🚛 ETS 2",
    "category": "🎮 Euro Truck Simulator 2",
    "slug": "ets-2",
    "display": "Euro Truck Simulator 2",
    "aliases": [
        "Euro Truck Simulator 2",
        "ETS 2",
        "ETS2"
    ],
    },
]

GAME_ROLE_NAMES = [g["role"] for g in GAMES]

ROLE_ORDER = [
    "👤 Member",
    "🔥 Aktif Üye",
    "💠 Elite",
    *GAME_ROLE_NAMES,
    "🔴 Streamer",
    "🛡️ Moderation Team",
    "🛠️ Admin",
    "⚡ Co-Owner",
    "👑 Founder",
]

BAD_WORDS = [
    "amk", "aq", "mk", "oc", "oç", "orospu", "piç", "pic",
    "sik", "siktir", "yarrak", "yarak", "göt", "got",
    "amcık", "amcik", "ibne", "gerizekalı", "gerizekali"
]

# =========================================================
# INTENTS
# Developer Portal > Bot > Privileged Gateway Intents:
# - Presence Intent
# - Server Members Intent
# - Message Content Intent
# açık olmalı
# =========================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================================================
# DATABASE
# =========================================================
def db():
    return sqlite3.connect(DB_FILE)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 0,
            last_gain REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS swear_counts (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ban_logs (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        banned_by INTEGER,
        reason TEXT,
        banned_at REAL NOT NULL,
        PRIMARY KEY (guild_id, user_id)
         )
     """)
    
    con.commit()
    con.close()

def ensure_level_user(guild_id: int, user_id: int):
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO levels (guild_id, user_id, xp, level, last_gain)
        VALUES (?, ?, 0, 0, 0)
    """, (guild_id, user_id))
    con.commit()
    con.close()

def get_level_user(guild_id: int, user_id: int):
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT xp, level, last_gain
        FROM levels
        WHERE guild_id=? AND user_id=?
    """, (guild_id, user_id))
    row = cur.fetchone()
    con.close()
    return row

def xp_needed_for_level(level: int) -> int:
    return 100 + (level * 50)

def can_gain_xp(guild_id: int, user_id: int) -> bool:
    row = get_level_user(guild_id, user_id)
    if not row:
        return True
    _, _, last_gain = row
    return (time.time() - last_gain) >= XP_COOLDOWN_SECONDS

def add_xp(guild_id: int, user_id: int, amount: int):
    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO levels (guild_id, user_id, xp, level, last_gain)
        VALUES (?, ?, 0, 0, 0)
    """, (guild_id, user_id))

    cur.execute("""
        SELECT xp, level
        FROM levels
        WHERE guild_id=? AND user_id=?
    """, (guild_id, user_id))
    xp, level = cur.fetchone()

    xp += amount
    leveled_up = False

    while xp >= xp_needed_for_level(level):
        xp -= xp_needed_for_level(level)
        level += 1
        leveled_up = True

    cur.execute("""
        UPDATE levels
        SET xp=?, level=?, last_gain=?
        WHERE guild_id=? AND user_id=?
    """, (xp, level, time.time(), guild_id, user_id))

    con.commit()
    con.close()
    return xp, level, leveled_up

def top_levels(guild_id: int, limit: int = 10):
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT user_id, level, xp
        FROM levels
        WHERE guild_id=?
        ORDER BY level DESC, xp DESC
        LIMIT ?
    """, (guild_id, limit))
    rows = cur.fetchall()
    con.close()
    return rows

def get_swear_count(guild_id: int, user_id: int) -> int:
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO swear_counts (guild_id, user_id, count)
        VALUES (?, ?, 0)
    """, (guild_id, user_id))
    cur.execute("""
        SELECT count
        FROM swear_counts
        WHERE guild_id=? AND user_id=?
    """, (guild_id, user_id))
    row = cur.fetchone()
    con.commit()
    con.close()
    return row[0] if row else 0

def increase_swear_count(guild_id: int, user_id: int) -> int:
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO swear_counts (guild_id, user_id, count)
        VALUES (?, ?, 0)
    """, (guild_id, user_id))
    cur.execute("""
        UPDATE swear_counts
        SET count = count + 1
        WHERE guild_id=? AND user_id=?
    """, (guild_id, user_id))
    cur.execute("""
        SELECT count
        FROM swear_counts
        WHERE guild_id=? AND user_id=?
    """, (guild_id, user_id))
    row = cur.fetchone()
    con.commit()
    con.close()
    return row[0] if row else 0

# =========================================================
# YARDIMCI
# =========================================================
def find_role(guild: discord.Guild, name: str):
    return discord.utils.get(guild.roles, name=name)

def find_category(guild: discord.Guild, name: str):
    return discord.utils.get(guild.categories, name=name)

def find_text_channel(guild: discord.Guild, name: str):
    return discord.utils.get(guild.text_channels, name=name)

def find_voice_channel(guild: discord.Guild, name: str):
    return discord.utils.get(guild.voice_channels, name=name)

def game_by_role(role_name: str):
    for game in GAMES:
        if game["role"] == role_name:
            return game
    return None

def game_by_activity_name(activity_name: str):
    low = activity_name.lower().strip()
    for game in GAMES:
        for alias in game["aliases"]:
            if alias.lower() == low:
                return game
    return None

def get_bot_member(guild: discord.Guild):
    if bot.user is None:
        return None
    return guild.me or guild.get_member(bot.user.id)

def bot_has_guild_permission(guild: discord.Guild, perm_name: str) -> bool:
    me = get_bot_member(guild)
    if me is None:
        return False
    return getattr(me.guild_permissions, perm_name, False)

async def get_or_create_role(guild: discord.Guild, name: str, permissions=None):
    role = find_role(guild, name)
    if role:
        return role

    if permissions is None:
        permissions = discord.Permissions.none()

    if not bot_has_guild_permission(guild, "manage_roles"):
        raise RuntimeError("Botta 'Rolleri Yönet' yetkisi yok.")

    try:
        return await guild.create_role(
            name=name,
            permissions=permissions,
            reason="Zental kurulum"
        )
    except discord.Forbidden:
        raise RuntimeError(
            "Rol oluşturulamadı. Botun 'Rolleri Yönet' izni yok veya bot rolü yeterince yukarıda değil."
        )

async def get_or_create_category(guild: discord.Guild, name: str, overwrites=None):
    category = find_category(guild, name)
    if category:
        return category

    if not bot_has_guild_permission(guild, "manage_channels"):
        raise RuntimeError("Botta 'Kanalları Yönet' yetkisi yok.")

    kwargs = {
        "name": name,
        "reason": "Zental kurulum"
    }

    if overwrites is not None:
        if not isinstance(overwrites, dict):
            raise RuntimeError(f"{name} kategorisi için overwrites dict olmalı.")
        kwargs["overwrites"] = overwrites

    try:
        return await guild.create_category(**kwargs)
    except discord.Forbidden:
        raise RuntimeError(f"{name} kategorisi oluşturulamadı. Kanal yetkilerini kontrol et.")

async def get_or_create_text_channel(
    guild: discord.Guild,
    category: discord.CategoryChannel,
    name: str,
    overwrites=None,
    topic=None
):
    channel = find_text_channel(guild, name)
    if channel:
        return channel

    if not bot_has_guild_permission(guild, "manage_channels"):
        raise RuntimeError("Botta 'Kanalları Yönet' yetkisi yok.")

    kwargs = {
        "name": name,
        "category": category,
        "reason": "Zental kurulum"
    }

    if overwrites is not None:
        if not isinstance(overwrites, dict):
            raise RuntimeError(f"{name} yazı kanalı için overwrites dict olmalı.")
        kwargs["overwrites"] = overwrites

    if topic is not None:
        kwargs["topic"] = topic

    try:
        return await guild.create_text_channel(**kwargs)
    except discord.Forbidden:
        raise RuntimeError(f"{name} yazı kanalı oluşturulamadı. Kanal yetkilerini kontrol et.")

async def get_or_create_voice_channel(
    guild: discord.Guild,
    category: discord.CategoryChannel,
    name: str,
    overwrites=None
):
    channel = find_voice_channel(guild, name)
    if channel:
        return channel

    if not bot_has_guild_permission(guild, "manage_channels"):
        raise RuntimeError("Botta 'Kanalları Yönet' yetkisi yok.")

    kwargs = {
        "name": name,
        "category": category,
        "reason": "Zental kurulum"
    }

    if overwrites is not None:
        if not isinstance(overwrites, dict):
            raise RuntimeError(f"{name} ses kanalı için overwrites dict olmalı.")
        kwargs["overwrites"] = overwrites

    try:
        return await guild.create_voice_channel(**kwargs)
    except discord.Forbidden:
        raise RuntimeError(f"{name} ses kanalı oluşturulamadı. Kanal yetkilerini kontrol et.")

async def set_role_positions(guild: discord.Guild):
    positions = {}
    base_position = 2

    for idx, role_name in enumerate(ROLE_ORDER):
        role = find_role(guild, role_name)
        if role:
            positions[role] = base_position + idx

    if positions:
        try:
            await guild.edit_role_positions(positions=positions)
        except discord.Forbidden:
            print("Rol sıralama hatası: Bot rolü yeterince yukarıda değil veya 'Rolleri Yönet' yetkisi yok.")
        except Exception as e:
            print("Rol sıralama hatası:", e)

async def apply_level_reward_roles(member: discord.Member, level: int):
    guild = member.guild
    aktif_role = find_role(guild, "🔥 Aktif Üye")
    elite_role = find_role(guild, "💠 Elite")

    to_add = []
    if level >= 5 and aktif_role and aktif_role not in member.roles:
        to_add.append(aktif_role)
    if level >= 15 and elite_role and elite_role not in member.roles:
        to_add.append(elite_role)

    if to_add:
        try:
            await member.add_roles(*to_add, reason="Seviye ödül rolü")
        except Exception as e:
            print("Seviye rolü verilemedi:", e)
# =========================================================
# AKILLI MODERASYON SİSTEMİ
# =========================================================

BLOCKED_LINK_WORDS = [
    "discord.gg",
    "discord.com/invite",
    "www.",
    "http://",
    "https://",
    ".com",
    ".net",
    ".org",
    ".gg"
]

SPAM_LIMIT = 5
SPAM_SECONDS = 5
CAPS_MIN_LENGTH = 12
CAPS_PERCENT = 0.70

message_cache = {}

weekly_game_task_started = False


async def handle_moderation(message: discord.Message):
    user_id = message.author.id
    now = time.time()
    content = message.content
    content_lower = content.lower()

    # SPAM KONTROL
    if user_id not in message_cache:
        message_cache[user_id] = []

    message_cache[user_id] = [
        t for t in message_cache[user_id]
        if now - t < SPAM_SECONDS
    ]
    message_cache[user_id].append(now)

    if len(message_cache[user_id]) >= SPAM_LIMIT:
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=2), reason="Spam")
            await message.channel.send(
                f"{message.author.mention} spam yapma 🚫 2 dakika susturuldun.",
                delete_after=7
            )
        except Exception as e:
            print("Spam moderasyon hatası:", e)
        return True

    # LİNK / REKLAM KONTROL
    if any(word in content_lower for word in BLOCKED_LINK_WORDS):
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=3), reason="Reklam / link")
            await message.channel.send(
                f"{message.author.mention} link/reklam yasak 🚫 3 dakika susturuldun.",
                delete_after=7
            )
        except Exception as e:
            print("Link moderasyon hatası:", e)
        return True

    # CAPS LOCK KONTROL
    if len(content) >= CAPS_MIN_LENGTH:
        letters = [c for c in content if c.isalpha()]
        if letters:
            upper_count = sum(1 for c in letters if c.isupper())
            if upper_count / len(letters) >= CAPS_PERCENT:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"{message.author.mention} büyük harfle yazma 😅",
                        delete_after=7
                    )
                except Exception as e:
                    print("Caps moderasyon hatası:", e)
                return True

        return False


# =========================================================
# HAFTALIK POPÜLER OYUN SİSTEMİ
# =========================================================

weekly_game_task_started = False


async def weekly_game_task():
    await bot.wait_until_ready()

    while not bot.is_closed():
        now = datetime.utcnow()

        # Pazartesi 12:00 UTC / Türkiye saatiyle yaklaşık 15:00
        if now.weekday() == 0 and now.hour == 12:
            for guild in bot.guilds:
                try:
                    one_week_ago = time.time() - (7 * 24 * 60 * 60)

                    con = db()
                    cur = con.cursor()
                    cur.execute("""
                        SELECT game_name, SUM(count) as total
                        FROM game_stats
                        WHERE guild_id=? AND last_seen>=?
                        GROUP BY game_slug, game_name
                        ORDER BY total DESC
                        LIMIT 3
                    """, (guild.id, one_week_ago))

                    rows = cur.fetchall()
                    con.close()

                    if not rows:
                        continue

                    lines = []
                    medals = ["🥇", "🥈", "🥉"]

                    for i, (game_name, total) in enumerate(rows):
                        lines.append(f"{medals[i]} **{game_name}** — {total} aktivite")

                    channel = find_text_channel(guild, "log")

                    if channel:
                        await channel.send(
                            "🏆 **HAFTALIK POPÜLER OYUN RAPORU**\n\n"
                            + "\n".join(lines)
                        )

                except Exception as e:
                    print("Haftalık oyun raporu hatası:", e)

            # Aynı saat içinde tekrar atmaması için 1 saat bekle
            await asyncio.sleep(3600)

        await asyncio.sleep(300)
    
# =========================================================
# YAYIN VE OYUN SPAM KORUMA VERİLERİ
# =========================================================
active_streams = set()
last_game_seen = {}
# =========================================================
# OYUN ROL BUTONLARI
# =========================================================
class GameRoleView1(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, interaction: discord.Interaction, role_name: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Bu işlem sadece sunucuda çalışır.", ephemeral=True)
            return

        role = find_role(interaction.guild, role_name)
        if not role:
            await interaction.response.send_message("Rol bulunamadı.", ephemeral=True)
            return

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Butonla rol kaldırma")
                await interaction.response.send_message(f"{role.name} rolü kaldırıldı.", ephemeral=True)
            else:
                await interaction.user.add_roles(role, reason="Butonla rol alma")
                await interaction.response.send_message(f"{role.name} rolü verildi.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Bot rol veremedi. Rol sırası veya yetkileri kontrol et.",
                ephemeral=True
            )

    @discord.ui.button(label="GTA V", style=discord.ButtonStyle.success, custom_id="role_gtav")
    async def btn_gtav(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "🎮 GTA V")

    @discord.ui.button(label="LoL", style=discord.ButtonStyle.primary, custom_id="role_lol")
    async def btn_lol(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "⚔️ LoL")

    @discord.ui.button(label="VALORANT", style=discord.ButtonStyle.danger, custom_id="role_valorant")
    async def btn_val(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "🎯 VALORANT")

    @discord.ui.button(label="CS2", style=discord.ButtonStyle.secondary, custom_id="role_cs2")
    async def btn_cs2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "🔫 CS2")

    @discord.ui.button(label="Minecraft", style=discord.ButtonStyle.success, custom_id="role_minecraft")
    async def btn_mc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "🧱 Minecraft")


class GameRoleView2(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, interaction: discord.Interaction, role_name: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Bu işlem sadece sunucuda çalışır.", ephemeral=True)
            return

        role = find_role(interaction.guild, role_name)
        if not role:
            await interaction.response.send_message("Rol bulunamadı.", ephemeral=True)
            return

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Butonla rol kaldırma")
                await interaction.response.send_message(f"{role.name} rolü kaldırıldı.", ephemeral=True)
            else:
                await interaction.user.add_roles(role, reason="Butonla rol alma")
                await interaction.response.send_message(f"{role.name} rolü verildi.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Bot rol veremedi. Rol sırası veya yetkileri kontrol et.",
                ephemeral=True
            )

    @discord.ui.button(label="Rust", style=discord.ButtonStyle.primary, custom_id="role_rust")
    async def btn_rust(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "☢️ Rust")

    @discord.ui.button(label="PUBG", style=discord.ButtonStyle.secondary, custom_id="role_pubg")
    async def btn_pubg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "🐔 PUBG")

    @discord.ui.button(label="PUBG Mobile", style=discord.ButtonStyle.secondary, custom_id="role_pubgmobile")
    async def btn_pubgm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "📱 PUBG Mobile")

    @discord.ui.button(label="Among Us", style=discord.ButtonStyle.secondary, custom_id="role_amongus")
    async def btn_amongus(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, "👨‍🚀 Among Us")

# =========================================================
# SETUP
# =========================================================
async def setup_views():
    bot.add_view(GameRoleView1())
    bot.add_view(GameRoleView2())


@bot.event
async def on_ready():
    init_db()

    global weekly_game_task_started
    if not weekly_game_task_started:
        bot.loop.create_task(weekly_game_task())
        weekly_game_task_started = True

    await setup_views()

    print(f"BOT DISCORD'A BAĞLANDI: {bot.user}")
    print("Bulunduğu sunucular:")
    for g in bot.guilds:
        print(f"- {g.name} | ID: {g.id}")

    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"GUILD_ID: {GUILD_ID}")
        print(f"Slash komut sayısı: {len(synced)}")
    except Exception as e:
        print("Sync hatası:", e)

# =========================================================
# ÜYE GİRİŞİ
# =========================================================
@bot.event
async def on_member_join(member: discord.Member):
    member_role = find_role(member.guild, "👤 Member")
    if member_role:
        try:
            await member.add_roles(member_role, reason="Otomatik üye rolü")
        except Exception:
            pass

    genel = find_text_channel(member.guild, "hoş-geldin")
    if genel:
        try:
            await genel.send(f"Gemiye biri bindi {member.mention} 🔥")
        except Exception:
            pass

# =========================================================
# OYUN DURUMU + YAYIN TAKİP SİSTEMİ
# =========================================================
@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if not after.guild or after.bot:
        return

    # =========================
    # YAYIN TAKİP SİSTEMİ
    # =========================
    streamer_role = find_role(after.guild, "🔴 Streamer")

    if streamer_role and streamer_role in after.roles:
        for activity in after.activities:
            if isinstance(activity, discord.Streaming):
                channel = find_text_channel(after.guild, "yayin-duyuru")

                if channel:
                    await channel.send(
                        f"🔴 **YAYIN BAŞLADI!**\n"
                        f"{after.mention} şimdi canlı yayında!\n"
                        f"🔗 İzle: {activity.url}"
                    )
                break

    # =========================
    # POPÜLER OYUN ALGILAMA
    # =========================
    for activity in after.activities:
        activity_name = getattr(activity, "name", None)
        if not activity_name:
            continue

        game = game_by_activity_name(activity_name)
        if not game:
            continue

        role = find_role(after.guild, game["role"])
        if role and role not in after.roles:
            try:
                await after.add_roles(role, reason="Popüler oyun algılandı")
            except Exception as e:
                print("Oyun rol hatası:", e)

        category = await get_or_create_category(after.guild, game["category"])

        await get_or_create_text_channel(
            after.guild,
            category,
            f"{game['slug']}-sohbet",
            topic=f"{game['display']} sohbet kanalı"
        )

        await get_or_create_text_channel(
            after.guild,
            category,
            f"{game['slug']}-takim-ara",
            topic=f"{game['display']} takım arkadaşı bulma"
        )

        for i in range(1, 9):
            await get_or_create_voice_channel(
                after.guild,
                category,
                f"{game['display']} {i}"
            )

        break
# =========================================================
# MESAJ: KÜFÜR + XP + AKILLI MODERASYON
# =========================================================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    if not isinstance(message.author, discord.Member):
        await bot.process_commands(message)
        return

    protected_roles = {"👑 Founder", "⚡ Co-Owner", "🛠️ Admin", "🛡️ Moderation Team"}
    content = message.content.lower()

    # AKILLI MODERASYON
    if not any(role.name in protected_roles for role in message.author.roles):
        blocked = await handle_moderation(message)
        if blocked:
            return

    # KÜFÜR SİSTEMİ
    if not any(role.name in protected_roles for role in message.author.roles):
        if any(word in content for word in BAD_WORDS):
            count = increase_swear_count(message.guild.id, message.author.id)

            try:
                await message.delete()
            except Exception:
                pass

            try:
                if count == 1:
                    await message.author.timeout(timedelta(minutes=5), reason="1. küfür - 5 dakika timeout")
                    await message.channel.send(
                        f"{message.author.mention} **küfür yasak.** 1. ceza: **5 dakika timeout**.",
                        delete_after=10
                    )

                elif count == 2:
                    await message.author.timeout(timedelta(minutes=10), reason="2. küfür - 10 dakika timeout")
                    await message.channel.send(
                        f"{message.author.mention} **küfür yasak.** 2. ceza: **10 dakika timeout**.",
                        delete_after=10
                    )

                elif count == 3:
                    await message.author.timeout(timedelta(minutes=30), reason="3. küfür - 30 dakika timeout")
                    await message.channel.send(
                        f"{message.author.mention} **küfür yasak.** 3. ceza: **30 dakika timeout**.",
                        delete_after=10
                    )

                else:
                    await message.guild.ban(message.author, reason="Tekrarlayan küfür - otomatik ban")
                    await message.channel.send(
                        f"{message.author.mention} tekrarlayan küfür nedeniyle **banlandı**.",
                        delete_after=10
                    )

                log_channel = find_text_channel(message.guild, "log")
                if log_channel:
                    await log_channel.send(
                        f"🤬 **KÜFÜR CEZASI**\n"
                        f"Kullanıcı: {message.author.mention}\n"
                        f"Küfür sayısı: **{count}**\n"
                        f"Kanal: {message.channel.mention}"
                    )

                await bot.process_commands(message)
                return

            except Exception as e:
                print("Küfür sistemi hatası:", e)

    # XP SİSTEMİ
    ensure_level_user(message.guild.id, message.author.id)

    if can_gain_xp(message.guild.id, message.author.id):
        xp, level, leveled_up = add_xp(
            message.guild.id,
            message.author.id,
            random.randint(15, 25)
        )

        if leveled_up:
            try:
                await apply_level_reward_roles(message.author, level)
                await message.channel.send(
                    f"🎉 {message.author.mention} seviye atladı: **{level}**",
                    delete_after=8
                )
            except Exception:
                pass

    await bot.process_commands(message)
    
# =========================================================
# /PING
# =========================================================
@bot.tree.command(name="ping", description="Bot çalışıyor mu test eder", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong")

# =========================================================
# /RANK
# =========================================================
@bot.tree.command(name="rank", description="Kendi seviyeni gösterir", guild=discord.Object(id=GUILD_ID))
async def rank(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Bu komut sadece sunucuda çalışır.", ephemeral=True)
        return

    ensure_level_user(interaction.guild.id, interaction.user.id)
    row = get_level_user(interaction.guild.id, interaction.user.id)
    xp, level, _ = row
    needed = xp_needed_for_level(level)

    embed = discord.Embed(title="Seviye Bilgin", color=discord.Color.blurple())
    embed.add_field(name="Kullanıcı", value=interaction.user.mention, inline=False)
    embed.add_field(name="Seviye", value=str(level), inline=True)
    embed.add_field(name="XP", value=f"{xp}/{needed}", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# =========================================================
# /LEADERBOARD
# =========================================================
@bot.tree.command(name="leaderboard", description="Seviye sıralaması", guild=discord.Object(id=GUILD_ID))
async def leaderboard(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Bu komut sadece sunucuda çalışır.", ephemeral=True)
        return

    rows = top_levels(interaction.guild.id, limit=10)
    if not rows:
        await interaction.response.send_message("Henüz veri yok.", ephemeral=True)
        return

    lines = []
    for i, (user_id, level, xp) in enumerate(rows, start=1):
        member = interaction.guild.get_member(user_id)
        name = member.mention if member else f"`{user_id}`"
        lines.append(f"**{i}.** {name} — Seviye **{level}** | XP **{xp}**")

    embed = discord.Embed(
        title="Zental Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed)
    
# =========================================================
# /PANEL
# =========================================================
@bot.tree.command(name="panel", description="Founder özel yönetim paneli", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction):
    if interaction.user.id != OWNER_USER_ID:
        await interaction.response.send_message("Bu panel sadece Founder içindir.", ephemeral=True)
        return

    if not interaction.guild:
        await interaction.response.send_message("Bu komut sadece sunucuda çalışır.", ephemeral=True)
        return

    await interaction.response.send_message("Panel özelden gönderildi.", ephemeral=True)

    guild = interaction.guild

    # Küfür kayıtları
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT user_id, count
        FROM swear_counts
        WHERE guild_id=?
        ORDER BY count DESC
        LIMIT 20
    """, (guild.id,))
    swear_rows = cur.fetchall()

    # Ban kayıtları
    cur.execute("""
        SELECT user_id, banned_by, reason
        FROM ban_logs
        WHERE guild_id=?
        ORDER BY banned_at DESC
        LIMIT 20
    """, (guild.id,))
    ban_rows = cur.fetchall()
    con.close()

    swear_lines = []
    if swear_rows:
        for user_id, count in swear_rows:
            member = guild.get_member(user_id)
            name = member.name if member else f"ID: {user_id}"
            swear_lines.append(f"• {name} — {count} küfür")
    else:
        swear_lines.append("Küfür kaydı yok.")

    ban_lines = []
    if ban_rows:
        for user_id, banned_by, reason in ban_rows:
            user_name = f"<@{user_id}>"
            admin_name = f"<@{banned_by}>" if banned_by else "Bilinmiyor"
            ban_lines.append(f"• {user_name} | Yetkili: {admin_name} | Sebep: {reason}")
    else:
        ban_lines.append("Ban kaydı yok.")

    embed = discord.Embed(
        title="🛡️ Zental Founder Panel",
        description=f"Sunucu: **{guild.name}**",
        color=discord.Color.dark_red()
    )

    embed.add_field(name="🤬 Küfür Kayıtları", value="\n".join(swear_lines)[:1024], inline=False)
    embed.add_field(name="🔨 Ban Kayıtları", value="\n".join(ban_lines)[:1024], inline=False)

    await interaction.user.send(embed=embed)


# =========================================================
# /BANAC
# =========================================================
@bot.tree.command(name="banac", description="Ban kaldır (sadece Founder)", guild=discord.Object(id=GUILD_ID))
async def banac(interaction: discord.Interaction, user_id: str):
    if interaction.user.id != OWNER_USER_ID:
        await interaction.response.send_message("Bu komutu sadece Founder kullanabilir.", ephemeral=True)
        return

    guild = interaction.guild

    try:
        user = await bot.fetch_user(int(user_id))
        await guild.unban(user)

        log_channel = find_text_channel(guild, "log")
        if log_channel:
            await log_channel.send(
                f"🔓 **BAN AÇILDI**\nKullanıcı: <@{user_id}>\nAçan: {interaction.user.mention}"
            )

        await interaction.response.send_message(f"{user} kullanıcısının banı açıldı.", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"Hata: {e}", ephemeral=True)
# =========================================================
# MODERASYON KOMUTLARI
# =========================================================

def is_staff(member: discord.Member) -> bool:
    allowed_roles = {"👑 Founder", "⚡ Co-Owner", "🛠️ Admin", "🛡️ Moderation Team"}
    return any(role.name in allowed_roles for role in member.roles)


@bot.command(name="ban")
async def ban(ctx, member: discord.Member, *, reason="Sebep yok"):
    if not is_staff(ctx.author):
        await ctx.send("Bu komutu kullanamazsın.")
        return

    try:
        await member.ban(reason=reason)

        con = db()
        cur = con.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO ban_logs (guild_id, user_id, banned_by, reason, banned_at)
            VALUES (?, ?, ?, ?, ?)
        """, (ctx.guild.id, member.id, ctx.author.id, reason, time.time()))
        con.commit()
        con.close()

        log_channel = find_text_channel(ctx.guild, "log")
        if log_channel:
            await log_channel.send(
                f"🔨 **BAN**\nKullanıcı: {member.mention}\nYetkili: {ctx.author.mention}\nSebep: {reason}"
            )

        await ctx.send(f"{member.mention} banlandı.")
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="kick")
async def kick(ctx, member: discord.Member, *, reason="Sebep yok"):
    if not is_staff(ctx.author):
        await ctx.send("Bu komutu kullanamazsın.")
        return

    try:
        await member.kick(reason=reason)

        log_channel = find_text_channel(ctx.guild, "log")
        if log_channel:
            await log_channel.send(
                f"👢 **KICK**\nKullanıcı: {member.mention}\nYetkili: {ctx.author.mention}\nSebep: {reason}"
            )

        await ctx.send(f"{member.mention} sunucudan atıldı.")
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="mute")
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason="Sebep yok"):
    if not is_staff(ctx.author):
        await ctx.send("Bu komutu kullanamazsın.")
        return

    try:
        await member.timeout(timedelta(minutes=minutes), reason=reason)

        log_channel = find_text_channel(ctx.guild, "log")
        if log_channel:
            await log_channel.send(
                f"🔇 **MUTE / TIMEOUT**\nKullanıcı: {member.mention}\nSüre: {minutes} dakika\nYetkili: {ctx.author.mention}\nSebep: {reason}"
            )

        await ctx.send(f"{member.mention} {minutes} dakika susturuldu.")
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="unmute")
async def unmute(ctx, member: discord.Member):
    if not is_staff(ctx.author):
        await ctx.send("Bu komutu kullanamazsın.")
        return

    try:
        await member.timeout(None, reason=f"Unmute yapan: {ctx.author}")

        log_channel = find_text_channel(ctx.guild, "log")
        if log_channel:
            await log_channel.send(
                f"🔊 **UNMUTE**\nKullanıcı: {member.mention}\nYetkili: {ctx.author.mention}"
            )

        await ctx.send(f"{member.mention} susturması kaldırıldı.")
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="temizle")
async def temizle(ctx, amount: int = 10):
    if not is_staff(ctx.author):
        await ctx.send("Bu komutu kullanamazsın.")
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)

        log_channel = find_text_channel(ctx.guild, "log")
        if log_channel:
            await log_channel.send(
                f"🧹 **MESAJ TEMİZLEME**\nKanal: {ctx.channel.mention}\nAdet: {len(deleted) - 1}\nYetkili: {ctx.author.mention}"
            )

        await ctx.send(f"{len(deleted) - 1} mesaj temizlendi.", delete_after=5)
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="warn")
async def warn(ctx, member: discord.Member, *, reason="Sebep yok"):
    if not is_staff(ctx.author):
        await ctx.send("Bu komutu kullanamazsın.")
        return

    log_channel = find_text_channel(ctx.guild, "log")
    if log_channel:
        await log_channel.send(
            f"⚠️ **UYARI**\nKullanıcı: {member.mention}\nYetkili: {ctx.author.mention}\nSebep: {reason}"
        )

    try:
        await member.send(f"⚠️ **{ctx.guild.name}** sunucusunda uyarı aldın.\nSebep: {reason}")
    except Exception:
        pass

    await ctx.send(f"{member.mention} uyarıldı. Sebep: {reason}")
# =========================================================
# /ROLPANEL
# =========================================================
@bot.tree.command(name="rolpanel", description="Oyun rol panelini tekrar yollar", guild=discord.Object(id=GUILD_ID))
async def rolpanel(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Bu komut sadece sunucuda çalışır.", ephemeral=True)
        return

    allowed = {"👑 Founder", "⚡ Co-Owner", "🛠️ Admin"}
    if not any(role.name in allowed for role in interaction.user.roles):
        await interaction.response.send_message("Yetkin yok.", ephemeral=True)
        return

    await interaction.channel.send("Oyun rollerini almak için butonlara bas:", view=GameRoleView1())
    await interaction.channel.send("Devam:", view=GameRoleView2())
    await interaction.response.send_message("Rol paneli gönderildi.", ephemeral=True)

# =========================================================
# /KUR
# =========================================================
@bot.tree.command(name="kur", description="Zental Community full kurulumunu yapar", guild=discord.Object(id=GUILD_ID))
async def kur(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Bu komut sadece sunucuda çalışır.", ephemeral=True)
        return

    if interaction.user.id != OWNER_USER_ID:
        await interaction.response.send_message("Bu komutu sadece bot sahibi kullanabilir.", ephemeral=True)
        return

    guild = interaction.guild
    await interaction.response.defer(ephemeral=True)

    try:
        if not bot_has_guild_permission(guild, "manage_roles"):
            await interaction.followup.send(
                "Botta **Rolleri Yönet** yetkisi yok. Sunucu Ayarları > Roller kısmından bot rolüne bu izni ver ve bot rolünü yukarı taşı.",
                ephemeral=True
            )
            return

        if not bot_has_guild_permission(guild, "manage_channels"):
            await interaction.followup.send(
                "Botta **Kanalları Yönet** yetkisi yok. Bu izni verip tekrar dene.",
                ephemeral=True
            )
            return

        founder_permissions = discord.Permissions(
            manage_guild=True,
            manage_roles=True,
            manage_channels=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            manage_messages=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
            mention_everyone=True,
            view_audit_log=True,
            manage_nicknames=True,
        )

        co_owner_permissions = discord.Permissions(
            manage_guild=True,
            manage_roles=True,
            manage_channels=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            manage_messages=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
            view_audit_log=True,
            manage_nicknames=True,
        )

        admin_permissions = discord.Permissions(
            manage_roles=True,
            manage_channels=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            manage_messages=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
            view_audit_log=True,
            manage_nicknames=True,
        )

        mod_permissions = discord.Permissions(
            kick_members=True,
            moderate_members=True,
            manage_messages=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
            manage_nicknames=True,
            view_audit_log=True,
        )

        member_permissions = discord.Permissions(
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            connect=True,
            speak=True,
            use_external_emojis=True,
            add_reactions=True,
            view_channel=True,
        )

        founder_role = await get_or_create_role(guild, "👑 Founder", founder_permissions)
        co_owner_role = await get_or_create_role(guild, "⚡ Co-Owner", co_owner_permissions)
        admin_role = await get_or_create_role(guild, "🛠️ Admin", admin_permissions)
        mod_role = await get_or_create_role(guild, "🛡️ Moderation Team", mod_permissions)
        member_role = await get_or_create_role(guild, "👤 Member", member_permissions)
        aktif_role = await get_or_create_role(guild, "🔥 Aktif Üye", member_permissions)
        elite_role = await get_or_create_role(guild, "💠 Elite", member_permissions)
        streamer_role = await get_or_create_role(guild, "🔴 Streamer", member_permissions)

        for game in GAMES:
            await get_or_create_role(guild, game["role"], member_permissions)

        await set_role_positions(guild)

        owner_member = guild.get_member(OWNER_USER_ID)
        if owner_member and founder_role not in owner_member.roles:
            try:
                await owner_member.add_roles(founder_role, reason="Founder rolü verildi")
            except Exception as e:
                print("Founder rol verilemedi:", e)

        co_owner_member = guild.get_member(CO_OWNER_USER_ID)
        if co_owner_member and co_owner_role not in co_owner_member.roles:
            try:
                await co_owner_member.add_roles(co_owner_role, reason="Co-Owner rolü verildi")
            except Exception as e:
                print("Co-Owner rol verilemedi:", e)

        everyone = guild.default_role

        info_cat = await get_or_create_category(guild, "📢 BİLGİ")
        community_cat = await get_or_create_category(guild, "💬 TOPLULUK")
        support_cat = await get_or_create_category(guild, "🛠️ DESTEK")
        stream_cat = await get_or_create_category(guild, "🎥 YAYIN")
        special_cat = await get_or_create_category(
            guild,
            "🔒 ÖZEL",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=False),
                founder_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True),
                co_owner_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True),
            }
        )

        await get_or_create_text_channel(
            guild, info_cat, "duyurular",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                founder_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                co_owner_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            },
            topic="Resmi sunucu duyuruları"
        )

        await get_or_create_text_channel(
            guild, info_cat, "kurallar",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                founder_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                co_owner_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            },
            topic="Sunucu kuralları"
        )

        await get_or_create_text_channel(
            guild, info_cat, "rol-al",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                founder_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                co_owner_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            },
            topic="Oyun rolü al"
        )

        await get_or_create_text_channel(guild, community_cat, "genel", topic="Genel sohbet")
        await get_or_create_text_channel(guild, community_cat, "mizah", topic="Mizah ve eğlence")
        await get_or_create_text_channel(guild, community_cat, "medya", topic="Klip, fotoğraf, video")
        await get_or_create_text_channel(guild, community_cat, "sohbet", topic="Serbest sohbet")
        await get_or_create_text_channel(guild, community_cat, "rank-ve-basari", topic="Seviye ve başarılar")
        await get_or_create_voice_channel(guild, community_cat, "Genel 1")
        await get_or_create_voice_channel(guild, community_cat, "Genel 2")
        await get_or_create_voice_channel(guild, community_cat, "Chill 1")
        await get_or_create_voice_channel(guild, community_cat, "Chill 2")       
        await get_or_create_text_channel(
            guild,
            support_cat,
            "log",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=False),
                founder_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                co_owner_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            },
            topic="Ban, küfür ve moderasyon logları"
        )

        await get_or_create_text_channel(guild, support_cat, "istek", topic="İstekler")
        await get_or_create_text_channel(guild, support_cat, "oneri", topic="Öneriler")
        await get_or_create_text_channel(guild, support_cat, "sikayet", topic="Şikayetler")
        await get_or_create_text_channel(guild, support_cat, "rapor", topic="Kural ihlali bildir")
        await get_or_create_text_channel(guild, support_cat, "destek", topic="Yardım ve destek")
        await get_or_create_text_channel(guild, support_cat, "arkadas-arayanlar", topic="Takım / arkadaş arayanlar")
        await get_or_create_text_channel(guild, support_cat, "etkinlik-fikirleri", topic="Etkinlik önerileri")

        await get_or_create_text_channel(
            guild, stream_cat, "yayin-duyuru",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                founder_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                co_owner_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                streamer_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            },
            topic="Yayın duyuruları"
        )

        await get_or_create_text_channel(guild, stream_cat, "yayinci-sohbet", topic="Yayıncı sohbet alanı")
        await get_or_create_voice_channel(guild, stream_cat, "Yayıncı Voice")

        await get_or_create_text_channel(
            guild, special_cat, "owner-chat",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=False),
                founder_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                co_owner_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            },
            topic="Sadece Founder ve Co-Owner"
        )

        await get_or_create_voice_channel(
            guild, special_cat, "Owner Voice",
            overwrites={
                everyone: discord.PermissionOverwrite(view_channel=False),
                founder_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
                co_owner_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
            }
        )

        for game in GAMES:
            cat = await get_or_create_category(guild, game["category"])

            await get_or_create_text_channel(
                guild, cat, f"{game['slug']}-sohbet",
                topic=f"{game['display']} yazılı sohbet"
            )

            await get_or_create_text_channel(
                guild, cat, f"{game['slug']}-takim-ara",
                topic=f"{game['display']} takım / arkadaş bulma"
            )

            for i in range(1, 9):
                await get_or_create_voice_channel(guild, cat, f"{game['display']} {i}")

        kurallar = find_text_channel(guild, "kurallar")
        if kurallar:
            try:
                history = [m async for m in kurallar.history(limit=1)]
                if not history:
                    await kurallar.send(
                        "• Saygılı ol\n"
                        "• Küfür etmek yasaktır\n"
                        "• Spam yasaktır\n"
                        "• Reklam yasaktır\n"
                        "• Kural ihlallerini #rapor kanalına bildir"
                    )
            except Exception:
                pass

        rolal = find_text_channel(guild, "rol-al")
        if rolal:
            try:
                existing = [m async for m in rolal.history(limit=5)]
                if not existing:
                    await rolal.send("Oyun rollerini almak için butonlara bas:")
                    await rolal.send("1. panel", view=GameRoleView1())
                    await rolal.send("2. panel", view=GameRoleView2())
            except Exception as e:
                print("Rol paneli gönderilemedi:", e)

        owner_chat = find_text_channel(guild, "owner-chat")
        if owner_chat:
            try:
                history = [m async for m in owner_chat.history(limit=1)]
                if not history:
                    await owner_chat.send("Burası sadece Founder ve Co-Owner için özel alandır.")
            except Exception:
                pass

        await interaction.followup.send("Zental Community full kurulum tamamlandı.", ephemeral=True)

    except RuntimeError as e:
        await interaction.followup.send(f"Kurulum durdu: {e}", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(
            "Discord yetki hatası oluştu. Bot rolünü en üste taşı ve Yönetici / Rolleri Yönet / Kanalları Yönet izinlerini aç.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"Beklenmeyen hata: {e}", ephemeral=True)
        print("Kurulum hatası:", e)
# =========================================================
# BAŞLAT
# =========================================================
bot.run(TOKEN)
