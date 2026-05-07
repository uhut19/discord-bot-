import os
import time
import random
import sqlite3
import asyncio
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

# KENDİ ID'LERİNİ BURAYA YAZ
GUILD_ID = 1496515150553944096
OWNER_USER_ID = 1365752307056119982
CO_OWNER_USER_ID = 1129879855492780153

DB_FILE = "zental.db"
XP_COOLDOWN_SECONDS = 60

# =========================================================
# OYUNLAR
# =========================================================
GAMES = [
    {"role": "🎮 GTA V", "category": "🎮 GTA V", "slug": "gta-v", "display": "GTA V", "aliases": ["Grand Theft Auto V", "Grand Theft Auto 5", "GTA V", "GTA 5"]},
    {"role": "⚔️ LoL", "category": "⚔️ League of Legends", "slug": "lol", "display": "League of Legends", "aliases": ["League of Legends", "LoL"]},
    {"role": "🎯 VALORANT", "category": "🎯 VALORANT", "slug": "valorant", "display": "VALORANT", "aliases": ["VALORANT"]},
    {"role": "🔫 CS2", "category": "🔫 Counter-Strike 2", "slug": "cs2", "display": "Counter-Strike 2", "aliases": ["Counter-Strike 2", "Counter Strike 2", "CS2"]},
    {"role": "🧱 Minecraft", "category": "🧱 Minecraft", "slug": "minecraft", "display": "Minecraft", "aliases": ["Minecraft"]},
    {"role": "☢️ Rust", "category": "☢️ Rust", "slug": "rust", "display": "Rust", "aliases": ["Rust"]},
    {"role": "🐔 PUBG", "category": "🐔 PUBG", "slug": "pubg", "display": "PUBG", "aliases": ["PUBG", "PUBG: BATTLEGROUNDS", "PLAYERUNKNOWN'S BATTLEGROUNDS"]},
    {"role": "📱 PUBG Mobile", "category": "📱 PUBG Mobile", "slug": "pubg-mobile", "display": "PUBG Mobile", "aliases": ["PUBG Mobile", "PUBG MOBILE"]},
    {"role": "👨‍🚀 Among Us", "category": "👨‍🚀 Among Us", "slug": "among-us", "display": "Among Us", "aliases": ["Among Us"]},
    {"role": "🚛 ETS 2", "category": "🚛 Euro Truck Simulator 2", "slug": "ets-2", "display": "Euro Truck Simulator 2", "aliases": ["Euro Truck Simulator 2", "ETS 2", "ETS2"]},
]

GAME_ROLE_NAMES = [g["role"] for g in GAMES]

ROLE_ORDER = [
    "❌ Kayıtsız",
    "👤 Üye",
    "👑 Prenses",
    "🎥 Yayıncı",
    "⚔️ Takım 1",
    "🔥 Aktif Üye",
    "💎 VIP",
    *GAME_ROLE_NAMES,
    "🛡️ Moderatör",
    "🔧 Admin",
    "⚡ Yönetici",
    "👑 Founder",
]

BAD_WORDS = [
    "amk", "aq", "mk", "oc", "oç", "orospu", "piç", "pic",
    "sik", "siktir", "yarrak", "yarak", "göt", "got",
    "amcık", "amcik", "ibne", "gerizekalı", "gerizekali"
]

BLOCKED_LINK_WORDS = [
    "discord.gg", "discord.com/invite", "http://", "https://",
    "www.", ".com", ".net", ".org", ".gg"
]

SPAM_LIMIT = 5
SPAM_SECONDS = 5
CAPS_MIN_LENGTH = 12
CAPS_PERCENT = 0.70

message_cache = {}

# =========================================================
# INTENTS
# Discord Developer Portal > Bot kısmından şunlar açık olmalı:
# Presence Intent, Server Members Intent, Message Content Intent
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
        CREATE TABLE IF NOT EXISTS warns (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            warn_count INTEGER NOT NULL DEFAULT 0,
            last_reason TEXT,
            last_warned_by INTEGER,
            last_warned_at REAL,
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
        SELECT count FROM swear_counts
        WHERE guild_id=? AND user_id=?
    """, (guild_id, user_id))
    row = cur.fetchone()
    con.commit()
    con.close()
    return row[0] if row else 0

# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================
def find_role(guild: discord.Guild, name: str):
    return discord.utils.get(guild.roles, name=name)


def find_category(guild: discord.Guild, name: str):
    return discord.utils.get(guild.categories, name=name)


def find_text_channel(guild: discord.Guild, name: str):
    return discord.utils.get(guild.text_channels, name=name)


def find_voice_channel(guild: discord.Guild, name: str):
    return discord.utils.get(guild.voice_channels, name=name)


def get_bot_member(guild: discord.Guild):
    if bot.user is None:
        return None
    return guild.me or guild.get_member(bot.user.id)


def bot_has_guild_permission(guild: discord.Guild, perm_name: str) -> bool:
    me = get_bot_member(guild)
    if me is None:
        return False
    return getattr(me.guild_permissions, perm_name, False)


def is_owner_or_co_owner(member: discord.Member) -> bool:
    return member.id in [OWNER_USER_ID, CO_OWNER_USER_ID]


def is_staff(member: discord.Member) -> bool:
    staff_roles = {"👑 Founder", "⚡ Yönetici", "🔧 Admin", "🛡️ Moderatör"}
    return member.guild_permissions.administrator or is_owner_or_co_owner(member) or any(role.name in staff_roles for role in member.roles)


def game_by_activity_name(activity_name: str):
    low = activity_name.lower().strip()
    for game in GAMES:
        for alias in game["aliases"]:
            if alias.lower() == low:
                return game
    return None


async def get_or_create_role(guild: discord.Guild, name: str, permissions=None):
    role = find_role(guild, name)
    if role:
        return role

    if permissions is None:
        permissions = discord.Permissions.none()

    return await guild.create_role(name=name, permissions=permissions, reason="Zental kurulum")


async def get_or_create_category(guild: discord.Guild, name: str, overwrites=None):
    category = find_category(guild, name)
    if category:
        if overwrites is not None:
            try:
                await category.edit(overwrites=overwrites)
            except Exception:
                pass
        return category

    return await guild.create_category(name=name, overwrites=overwrites, reason="Zental kurulum")


async def get_or_create_text_channel(guild: discord.Guild, category: discord.CategoryChannel, name: str, overwrites=None, topic=None):
    channel = find_text_channel(guild, name)
    if channel:
        try:
            await channel.edit(category=category, overwrites=overwrites, topic=topic)
        except Exception:
            pass
        return channel

    return await guild.create_text_channel(
        name=name,
        category=category,
        overwrites=overwrites,
        topic=topic,
        reason="Zental kurulum"
    )


async def get_or_create_voice_channel(guild: discord.Guild, category: discord.CategoryChannel, name: str, overwrites=None, user_limit=None):
    channel = find_voice_channel(guild, name)
    if channel:
        try:
            await channel.edit(category=category, overwrites=overwrites, user_limit=user_limit)
        except Exception:
            pass
        return channel

    return await guild.create_voice_channel(
        name=name,
        category=category,
        overwrites=overwrites,
        user_limit=user_limit,
        reason="Zental kurulum"
    )


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
        except Exception as e:
        import traceback
        traceback.print_exc()

        print(f"/kur hatası: {e}")

        try:
            await interaction.followup.send(
                f"Kurulum hatası: {e}",
                ephemeral=True
            )
        except:
            pass

    channel = find_text_channel(member.guild, "👋・hos-geldin") or find_text_channel(member.guild, "hos-geldin")
    if channel:
        try:
            await channel.send(f"🚀 Zental'a hoş geldin {member.mention}! Kayıt olmak için kayıt kanalına bak.")
        except Exception:
            pass


@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if not after.guild or after.bot:
        return

    streamer_role = find_role(after.guild, "🎥 Yayıncı")
    if streamer_role and streamer_role in after.roles:
        for activity in after.activities:
            if isinstance(activity, discord.Streaming):
                channel = find_text_channel(after.guild, "📡・yayin-duyuru") or find_text_channel(after.guild, "yayin-duyuru")
                if channel:
                    await channel.send(
                        f"🔴 **YAYIN BAŞLADI!**\n"
                        f"{after.mention} şu an canlı yayında!\n"
                        f"🔗 İzle: {activity.url}"
                    )
                break

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
                await after.add_roles(role, reason="Oyun aktivitesi algılandı")
            except Exception as e:
                print("Oyun rol hatası:", e)
        break


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    if not isinstance(message.author, discord.Member):
        await bot.process_commands(message)
        return

    content = message.content.lower()

    if not is_staff(message.author):
        blocked = await handle_moderation(message)
        if blocked:
            return

        if any(word in content for word in BAD_WORDS):
            count = increase_swear_count(message.guild.id, message.author.id)

            try:
                await message.delete()
            except Exception:
                pass

            try:
                if count == 1:
                    await message.author.timeout(timedelta(minutes=5), reason="1. küfür")
                    ceza = "5 dakika timeout"
                elif count == 2:
                    await message.author.timeout(timedelta(minutes=10), reason="2. küfür")
                    ceza = "10 dakika timeout"
                elif count == 3:
                    await message.author.timeout(timedelta(minutes=30), reason="3. küfür")
                    ceza = "30 dakika timeout"
                else:
                    await message.guild.ban(message.author, reason="Tekrarlayan küfür")
                    ceza = "kalıcı ban"

                await message.channel.send(
                    f"{message.author.mention} küfür yasak. Ceza: **{ceza}**.",
                    delete_after=10
                )

                log_channel = find_text_channel(message.guild, "📋・log") or find_text_channel(message.guild, "log")
                if log_channel:
                    await log_channel.send(
                        f"🤬 **KÜFÜR CEZASI**\n"
                        f"Kullanıcı: {message.author.mention}\n"
                        f"Küfür Sayısı: **{count}**\n"
                        f"Ceza: **{ceza}**\n"
                        f"Kanal: {message.channel.mention}"
                    )
                return
            except Exception as e:
                print("Küfür sistemi hatası:", e)

    ensure_level_user(message.guild.id, message.author.id)
    if can_gain_xp(message.guild.id, message.author.id):
        xp, level, leveled_up = add_xp(message.guild.id, message.author.id, random.randint(15, 25))
        if leveled_up:
            try:
                await apply_level_reward_roles(message.author, level)
                await message.channel.send(f"🎉 {message.author.mention} seviye atladı: **{level}**", delete_after=8)
            except Exception:
                pass

    await bot.process_commands(message)

# =========================================================
# SLASH KOMUTLAR
# =========================================================
@bot.tree.command(name="ping", description="Bot çalışıyor mu test eder", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong ✅", ephemeral=True)


@bot.tree.command(name="rank", description="Kendi seviyeni gösterir", guild=discord.Object(id=GUILD_ID))
async def rank(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Bu komut sadece sunucuda çalışır.", ephemeral=True)
        return

    ensure_level_user(interaction.guild.id, interaction.user.id)
    xp, level, _ = get_level_user(interaction.guild.id, interaction.user.id)
    needed = xp_needed_for_level(level)

    embed = discord.Embed(title="📊 Seviye Bilgin", color=discord.Color.blurple())
    embed.add_field(name="Kullanıcı", value=interaction.user.mention, inline=False)
    embed.add_field(name="Seviye", value=str(level), inline=True)
    embed.add_field(name="XP", value=f"{xp}/{needed}", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


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

    embed = discord.Embed(title="🏆 Zental Leaderboard", description="\n".join(lines), color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rolpanel", description="Oyun rol panelini yollar", guild=discord.Object(id=GUILD_ID))
async def rolpanel(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Bu komut sadece sunucuda çalışır.", ephemeral=True)
        return

    if not is_staff(interaction.user):
        await interaction.response.send_message("Yetkin yok.", ephemeral=True)
        return

    await interaction.channel.send("🎮 Oyun rollerini almak için butonlara bas:", view=GameRoleView1())
    await interaction.channel.send("🎮 Devam:", view=GameRoleView2())
    await interaction.response.send_message("Rol paneli gönderildi.", ephemeral=True)


@bot.tree.command(name="kayitpanel", description="Kayıt panelini gönderir", guild=discord.Object(id=GUILD_ID))
async def kayitpanel(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
        await interaction.response.send_message("Yetkin yok.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📥 Zental Kayıt Sistemi",
        description="Sunucuya tam erişim için aşağıdaki butona bas.\n\nYeni gelen üyeler eski mesajları göremez; kayıt olduktan sonra yeni mesajlardan itibaren sohbete katılır.",
        color=discord.Color.green()
    )
    await interaction.channel.send(embed=embed, view=RegisterView())
    await interaction.response.send_message("Kayıt paneli gönderildi.", ephemeral=True)


@bot.tree.command(name="guncelle", description="Kurallar metnini günceller", guild=discord.Object(id=GUILD_ID))
async def guncelle(interaction: discord.Interaction):
    if interaction.user.id != OWNER_USER_ID:
        await interaction.response.send_message("Bu komutu sadece Founder kullanabilir.", ephemeral=True)
        return

    if not interaction.guild:
        await interaction.response.send_message("Bu komut sadece sunucuda çalışır.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    kurallar = find_text_channel(interaction.guild, "📜・kurallar") or find_text_channel(interaction.guild, "kurallar")
    if not kurallar:
        await interaction.followup.send("Kurallar kanalı bulunamadı.", ephemeral=True)
        return

    try:
        async for msg in kurallar.history(limit=50):
            if msg.author == interaction.guild.me:
                await msg.delete()

        await send_rules(kurallar)
        await interaction.followup.send("Kurallar güncellendi.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Güncelleme hatası: {e}", ephemeral=True)


@bot.tree.command(name="kur", description="Zental sunucusunu sıfırdan kurar", guild=discord.Object(id=GUILD_ID))
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
            await interaction.followup.send("Botta **Rolleri Yönet** yetkisi yok. Bot rolünü en üste yakın taşı.", ephemeral=True)
            return

        if not bot_has_guild_permission(guild, "manage_channels"):
            await interaction.followup.send("Botta **Kanalları Yönet** yetkisi yok.", ephemeral=True)
            return

        await interaction.followup.send("Kurulum başladı. Eski roller siliniyor, yeni sistem kuruluyor...", ephemeral=True)

        # GÜVENLİ KURULUM KANALI OLUŞTUR
        guvenli_kategori = discord.utils.get(guild.categories, name="⚙️ ZENTAL KURULUM")

        if not guvenli_kategori:
            guvenli_kategori = await guild.create_category(
                name="⚙️ ZENTAL KURULUM",
                reason="Zental güvenli kurulum sistemi"
            )

        guvenli_kanal = discord.utils.get(guild.text_channels, name="🛠️・kurulum-log")

        if not guvenli_kanal:
            guvenli_kanal = await guild.create_text_channel(
                name="🛠️・kurulum-log",
                category=guvenli_kategori,
                reason="Zental güvenli kurulum sistemi"
            )

        await guvenli_kanal.send("⚙️ Zental kurulumu başladı. Sunucu sıfırlanıyor...")

        # TÜM KATEGORİ VE KANALLARI SİL
        channels_to_delete = [
            c for c in guild.channels
            if c.id != guvenli_kanal.id and c.id != guvenli_kategori.id
        ]

        for channel in channels_to_delete:
            try:
                await channel.delete(reason="Zental tam sıfırlama")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Kanal silinemedi: {channel.name} | {e}")

        await guvenli_kanal.send("🧹 Eski kanallar silindi. Discord cache temizleniyor...")
        print("Kanallar silindi, Discord cache temizleniyor...")
        await asyncio.sleep(10)

        try:
            await guvenli_kanal.send("🚀 Yeni Zental sistemi kuruluyor...")
        except Exception:
            pass

        # TÜM ROLLERİ SİL
        await delete_old_roles(guild)

        # HERKESİN ROLLERİNİ SIFIRLA
        for member in guild.members:
            try:
                roles_to_remove = [r for r in member.roles if not r.is_default()]
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Zental tam sıfırlama")
                    await asyncio.sleep(0.2)
            except Exception as e:
                print(f"Rol sıfırlama hatası: {member} | {e}")

        # PERMISSIONS
        founder_permissions = discord.Permissions.all()

        yonetici_permissions = discord.Permissions(
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
            mention_everyone=True,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            connect=True,
            speak=True,
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
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            connect=True,
            speak=True,
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
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            connect=True,
            speak=True,
        )

        member_permissions = discord.Permissions(
            view_channel=True,
            send_messages=True,
            read_message_history=False,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
            connect=True,
            speak=True,
            use_external_emojis=True,
        )

        # ROLLER
        kayitsiz_role = await get_or_create_role(guild, "❌ Kayıtsız", discord.Permissions(view_channel=True, read_message_history=False))
        uye_role = await get_or_create_role(guild, "👤 Üye", member_permissions)
        prenses_role = await get_or_create_role(guild, "👑 Prenses", member_permissions)
        yayinci_role = await get_or_create_role(guild, "🎥 Yayıncı", member_permissions)
        takim1_role = await get_or_create_role(guild, "⚔️ Takım 1", member_permissions)
        aktif_role = await get_or_create_role(guild, "🔥 Aktif Üye", member_permissions)
        vip_role = await get_or_create_role(guild, "💎 VIP", member_permissions)

        for game in GAMES:
            await get_or_create_role(guild, game["role"], member_permissions)

        mod_role = await get_or_create_role(guild, "🛡️ Moderatör", mod_permissions)
        admin_role = await get_or_create_role(guild, "🔧 Admin", admin_permissions)
        yonetici_role = await get_or_create_role(guild, "⚡ Yönetici", yonetici_permissions)
        founder_role = await get_or_create_role(guild, "👑 Founder", founder_permissions)

        await set_role_positions(guild)

        # NOT: Sana ve yönetici arkadaşına otomatik rol atamaz.
        # Rolleri Discord üzerinden elle ver.

        everyone = guild.default_role

        no_history_everyone = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=False)
        read_only_everyone = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
        hidden_everyone = discord.PermissionOverwrite(view_channel=False)

        staff_overwrite = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True)
        member_overwrite = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=False, connect=True, speak=True)

        # KATEGORİLER
        info_cat = await get_or_create_category(guild, "📢 BİLGİ")
        community_cat = await get_or_create_category(guild, "💬 TOPLULUK")
        voice_cat = await get_or_create_category(guild, "🔊 SES ODALARI")
        team_cat = await get_or_create_category(guild, "⚔️ TAKIM 1", overwrites={
            everyone: hidden_everyone,
            takim1_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=False, connect=True, speak=True),
            founder_role: staff_overwrite,
            yonetici_role: staff_overwrite,
            admin_role: staff_overwrite,
        })
        support_cat = await get_or_create_category(guild, "🛠️ DESTEK")
        stream_cat = await get_or_create_category(guild, "🎥 YAYIN")
        special_cat = await get_or_create_category(guild, "🔒 YÖNETİM", overwrites={
            everyone: hidden_everyone,
            founder_role: staff_overwrite,
            yonetici_role: staff_overwrite,
            admin_role: staff_overwrite,
            mod_role: staff_overwrite,
        })

        # BİLGİ KANALLARI
        await get_or_create_text_channel(guild, info_cat, "👋・hos-geldin", overwrites={everyone: read_only_everyone, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite}, topic="Hoş geldin mesajları")

        kurallar_channel = await get_or_create_text_channel(guild, info_cat, "📜・kurallar", overwrites={everyone: read_only_everyone, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite}, topic="Sunucu kuralları")

        await get_or_create_text_channel(guild, info_cat, "📢・duyurular", overwrites={everyone: read_only_everyone, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="Resmi duyurular")

        await get_or_create_text_channel(guild, info_cat, "✅・kayit", overwrites={everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True), founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite}, topic="Kayıt paneli")

        await get_or_create_text_channel(guild, info_cat, "🎮・rol-al", overwrites={everyone: read_only_everyone, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite}, topic="Oyun rolleri")

        await get_or_create_text_channel(guild, info_cat, "📣・reklam", overwrites={
            everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=False),
            founder_role: staff_overwrite,
            yonetici_role: staff_overwrite,
        }, topic="Reklam kanalı. Sadece Founder ve Yönetici paylaşım yapabilir.")

        # TOPLULUK KANALLARI
        await get_or_create_text_channel(guild, community_cat, "💬・genel", overwrites={everyone: no_history_everyone, uye_role: member_overwrite, prenses_role: member_overwrite, yayinci_role: member_overwrite, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="Genel sohbet")
        await get_or_create_text_channel(guild, community_cat, "😂・mizah", overwrites={everyone: no_history_everyone, uye_role: member_overwrite, prenses_role: member_overwrite, yayinci_role: member_overwrite, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="Mizah ve eğlence")
        await get_or_create_text_channel(guild, community_cat, "📸・medya", overwrites={everyone: no_history_everyone, uye_role: member_overwrite, prenses_role: member_overwrite, yayinci_role: member_overwrite, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="Klip, fotoğraf ve video")
        await get_or_create_text_channel(guild, community_cat, "🏆・rank-basari", overwrites={everyone: no_history_everyone, uye_role: member_overwrite, prenses_role: member_overwrite, yayinci_role: member_overwrite, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="Rank ve başarılar")

        # 5 SES KANALI + AFK + MÜZİK
        await get_or_create_voice_channel(guild, voice_cat, "🎧・Genel Sohbet", overwrites={everyone: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)})
        await get_or_create_voice_channel(guild, voice_cat, "🔥・Aktif Oda", overwrites={everyone: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)})
        await get_or_create_voice_channel(guild, voice_cat, "⚔️・Takım Kur", overwrites={everyone: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)})
        await get_or_create_voice_channel(guild, voice_cat, "🎵・Müzik Odası", overwrites={everyone: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)})
        afk_channel = await get_or_create_voice_channel(guild, voice_cat, "💤・AFK", overwrites={everyone: discord.PermissionOverwrite(view_channel=True, connect=True, speak=False)})

        try:
            await guild.edit(afk_channel=afk_channel, afk_timeout=300)
        except Exception:
            pass

        # TAKIM 1 ÖZEL
        await get_or_create_text_channel(guild, team_cat, "⚔️・takim-1-chat", overwrites={
            everyone: hidden_everyone,
            takim1_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=False),
            founder_role: staff_overwrite,
            yonetici_role: staff_overwrite,
            admin_role: staff_overwrite,
        }, topic="Sadece Takım 1 özel sohbet")

        await get_or_create_voice_channel(guild, team_cat, "⚔️・Takım 1 Voice", overwrites={
            everyone: hidden_everyone,
            takim1_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
            founder_role: staff_overwrite,
            yonetici_role: staff_overwrite,
            admin_role: staff_overwrite,
        })

        # DESTEK / LOG
        await get_or_create_text_channel(guild, support_cat, "📋・log", overwrites={everyone: hidden_everyone, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="Moderasyon logları")
        await get_or_create_text_channel(guild, support_cat, "📝・istek-oneri", overwrites={everyone: no_history_everyone, uye_role: member_overwrite, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="İstek ve öneriler")
        await get_or_create_text_channel(guild, support_cat, "🚨・sikayet", overwrites={everyone: no_history_everyone, uye_role: member_overwrite, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="Şikayet ve rapor")

        # YAYIN
        await get_or_create_text_channel(guild, stream_cat, "📡・yayin-duyuru", overwrites={everyone: read_only_everyone, yayinci_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True), founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite}, topic="Yayın duyuruları")
        await get_or_create_text_channel(guild, stream_cat, "🎥・yayinci-sohbet", overwrites={everyone: no_history_everyone, yayinci_role: member_overwrite, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite}, topic="Yayıncı sohbet")
        await get_or_create_voice_channel(guild, stream_cat, "📡・Yayıncı Voice", overwrites={everyone: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True), yayinci_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)})

        # YÖNETİM
        await get_or_create_text_channel(guild, special_cat, "👑・yonetim-chat", overwrites={everyone: hidden_everyone, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite}, topic="Yönetim özel chat")
        await get_or_create_voice_channel(guild, special_cat, "👑・Yönetim Voice", overwrites={everyone: hidden_everyone, founder_role: staff_overwrite, yonetici_role: staff_overwrite, admin_role: staff_overwrite, mod_role: staff_overwrite})

        # OYUN KATEGORİLERİ
        voice_emojis = ["🎧", "🔥", "⚔️", "🎮", "💀"]
        for game in GAMES:
            game_role = find_role(guild, game["role"])
            game_cat = await get_or_create_category(guild, game["category"], overwrites={
                everyone: discord.PermissionOverwrite(view_channel=True, read_message_history=False),
                game_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=False, connect=True, speak=True),
                founder_role: staff_overwrite,
                yonetici_role: staff_overwrite,
                admin_role: staff_overwrite,
                mod_role: staff_overwrite,
            })

            await get_or_create_text_channel(guild, game_cat, f"💬・{game['slug']}-sohbet", topic=f"{game['display']} sohbet")
            await get_or_create_text_channel(guild, game_cat, f"🤝・{game['slug']}-takim-ara", topic=f"{game['display']} takım bulma")

            for i in range(5):
                await get_or_create_voice_channel(guild, game_cat, f"{voice_emojis[i]}・{game['display']} {i + 1}")

        # KURALLAR VE PANELLER
        await send_rules(kurallar_channel)

        rol_al = find_text_channel(guild, "🎮・rol-al")
        if rol_al:
            await rol_al.send("🎮 Oyun rollerini almak için butonlara bas:", view=GameRoleView1())
            await rol_al.send("🎮 Devam:", view=GameRoleView2())

        kayit = find_text_channel(guild, "✅・kayit")
        if kayit:
            embed = discord.Embed(
                title="📥 Zental Kayıt Sistemi",
                description="Sunucuya erişim için aşağıdaki butona bas.\n\nYeni gelen üyeler eski mesajları göremez; kayıt olduktan sonra yeni mesajlardan itibaren sohbete katılır.",
                color=discord.Color.green()
            )
            await kayit.send(embed=embed, view=RegisterView())

        await interaction.followup.send("✅ Zental kurulumu tamamlandı. Sana ve yönetici arkadaşına otomatik rol verilmedi; rolleri elle ver.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"Kurulum hatası: {e}", ephemeral=True)
        print("/kur hatası:", e)

# =========================================================
# KURALLAR METNİ
# =========================================================
async def send_rules(channel: discord.TextChannel):
    await channel.send(
        "📜 **ZENTAL SUNUCU KURALLARI**\n\n"
        "Zental Community düzenli, saygılı ve aktif oyuncuların bulunduğu bir topluluktur. Sunucuda bulunan herkes aşağıdaki kuralları kabul etmiş sayılır.\n\n"
        "1️⃣ **Saygı zorunludur.**\n"
        "Hakaret, aşağılama, kışkırtma, dalga geçme, tehdit, hedef gösterme ve huzur bozma yasaktır.\n\n"
        "2️⃣ **Küfür ve ağır argo yasaktır.**\n"
        "Küfür sistemi aktiftir. Küfür eden kişiler otomatik timeout alır. Tekrarlayan ihlaller kalıcı ban ile sonuçlanabilir.\n\n"
        "3️⃣ **Ailevi, dini ve milli değerlere hakaret ağır ihlaldir.**\n"
        "Bu tarz ihlallerde uyarı beklenmeden ciddi yaptırım uygulanabilir.\n\n"
        "4️⃣ **Reklam ve link paylaşımı yasaktır.**\n"
        "Discord davet linki, satış linki, sosyal medya reklamı, kanal tanıtımı ve izinsiz bağlantı paylaşımı yasaktır. Reklam sadece `📣・reklam` kanalında ve sadece yetkililer tarafından yapılabilir.\n\n"
        "5️⃣ **Spam, flood ve CAPS yasaktır.**\n"
        "Arka arkaya mesaj atmak, gereksiz etiket kullanmak ve tamamen büyük harfle yazmak yasaktır.\n\n"
        "6️⃣ **+18, uygunsuz ve rahatsız edici içerik yasaktır.**\n"
        "Cinsel içerik, şiddet içerikli görsel, rahatsız edici video, uygunsuz profil veya isim kullanımı yasaktır.\n\n"
        "7️⃣ **Ses kanallarında huzur bozmak yasaktır.**\n"
        "Bağırmak, mikrofon basmak, ses kasıtlı bozmak, müzik açıp rahatsız etmek ve odaları sabote etmek yasaktır.\n\n"
        "8️⃣ **Takım odaları özel alanlardır.**\n"
        "`⚔️ Takım 1` rolüne ait özel kanallar sadece ilgili takım içindir. Yetkisiz kullanım veya rahatsız etme yasaktır.\n\n"
        "9️⃣ **Yetkililere saygı zorunludur.**\n"
        "Yetkili kararlarına karşı hakaret, tartışma çıkarmak veya manipülasyon yapmak ceza sebebidir. İtirazlar sakin şekilde yapılmalıdır.\n\n"
        "🔟 **Ceza sistemi**\n"
        "• 1. küfür: 5 dakika timeout\n"
        "• 2. küfür: 10 dakika timeout\n"
        "• 3. küfür: 30 dakika timeout\n"
        "• Tekrarlayan ihlal: kalıcı ban\n"
        "• 3 warn: 30 dakika timeout\n"
        "• 5 warn: kalıcı ban\n\n"
        "⚠️ **Ciddi yaptırımlar uygulanır.**\n"
        "Kuralları ihlal eden kullanıcılar timeout, rol kaldırma, kanallardan men, kick, kalıcı ban veya kara liste cezası alabilir. Ağır ihlallerde uyarı yapılmadan direkt işlem uygulanabilir.\n\n"
        "👑 **Son karar yetkililere aittir.**\n"
        "Sunucuda düzeni korumak için Founder ve Yönetim ekibi gerekli gördüğü işlemi uygulama hakkına sahiptir."
    )

# =========================================================
# PREFIX KOMUTLAR
# =========================================================
@bot.command(name="kufurekle")
async def kufurekle(ctx, *, kelime: str):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("Yetkin yok.")
        return

    kelime = kelime.lower().strip()
    if not kelime:
        await ctx.send("Kelime boş olamaz.")
        return

    if kelime in BAD_WORDS:
        await ctx.send("Bu kelime zaten küfür listesinde.")
        return

    BAD_WORDS.append(kelime)
    await ctx.send(f"✅ `{kelime}` küfür listesine eklendi.")


@bot.command(name="kufurliste")
async def kufurliste(ctx):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("Yetkin yok.")
        return

    await ctx.send("🤬 **Küfür Listesi:**\n" + ", ".join(f"`{w}`" for w in BAD_WORDS))


@bot.command(name="temizle")
async def temizle(ctx, amount: int = 10):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("Yetkin yok.")
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"🧹 {len(deleted) - 1} mesaj temizlendi.", delete_after=5)
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="warn")
async def warn(ctx, member: discord.Member, *, reason="Sebep yok"):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("Yetkin yok.")
        return

    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO warns (guild_id, user_id, warn_count)
        VALUES (?, ?, 0)
    """, (ctx.guild.id, member.id))
    cur.execute("""
        UPDATE warns
        SET warn_count = warn_count + 1,
            last_reason = ?,
            last_warned_by = ?,
            last_warned_at = ?
        WHERE guild_id=? AND user_id=?
    """, (reason, ctx.author.id, time.time(), ctx.guild.id, member.id))
    cur.execute("SELECT warn_count FROM warns WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id))
    warn_count = cur.fetchone()[0]
    con.commit()
    con.close()

    action_text = ""
    try:
        if warn_count == 3:
            await member.timeout(timedelta(minutes=30), reason="3 warn")
            action_text = "🔇 30 dakika susturuldu"
        elif warn_count >= 5:
            await member.ban(reason="5 warn")
            action_text = "🔨 banlandı"
    except Exception as e:
        print("Warn ceza hatası:", e)

    log_channel = find_text_channel(ctx.guild, "📋・log") or find_text_channel(ctx.guild, "log")
    if log_channel:
        await log_channel.send(
            f"⚠️ **WARN**\n"
            f"Kullanıcı: {member.mention}\n"
            f"Yetkili: {ctx.author.mention}\n"
            f"Sebep: {reason}\n"
            f"Toplam Warn: **{warn_count}**\n"
            f"{action_text}"
        )

    await ctx.send(f"{member.mention} uyarıldı. Toplam warn: **{warn_count}** {action_text}")


@bot.command(name="mute")
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason="Sebep yok"):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("Yetkin yok.")
        return

    try:
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        await ctx.send(f"🔇 {member.mention} {minutes} dakika susturuldu.")
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="unmute")
async def unmute(ctx, member: discord.Member):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("Yetkin yok.")
        return

    try:
        await member.timeout(None, reason=f"Unmute yapan: {ctx.author}")
        await ctx.send(f"🔊 {member.mention} susturması kaldırıldı.")
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="kick")
async def kick(ctx, member: discord.Member, *, reason="Sebep yok"):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("Yetkin yok.")
        return

    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.mention} sunucudan atıldı.")
    except Exception as e:
        await ctx.send(f"Hata: {e}")


@bot.command(name="ban")
async def ban(ctx, member: discord.Member, *, reason="Sebep yok"):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send("Yetkin yok.")
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
        await ctx.send(f"🔨 {member.mention} banlandı.")
    except Exception as e:
        await ctx.send(f"Hata: {e}")

# =========================================================
# BOTU BAŞLAT
# =========================================================
bot.run(TOKEN)
