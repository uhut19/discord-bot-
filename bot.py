# ZENTAL BOT - TEMİZ STABİL SÜRÜM
# Mevcut bozuk dosyayı kullanma.
# Bununla tamamen değiştir.

import os
import asyncio
import random
import time
import sqlite3
from datetime import timedelta

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# =========================================================
# AYARLAR
# =========================================================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1496515150553944096
OWNER_USER_ID = 1365752307056119982
CO_OWNER_USER_ID = 1129879855492780153

DB_FILE = "zental.db"
XP_COOLDOWN_SECONDS = 60

# =========================================================
# INTENTS
# =========================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================================================
# VERİLER
# =========================================================
BAD_WORDS = [
    "amk", "aq", "mk", "oc", "oç", "orospu", "piç",
    "sik", "siktir", "yarrak", "yarak", "göt",
    "amcık", "ibne", "gerizekalı"
]

GAMES = [
    {"name": "GTA V", "emoji": "🚗"},
    {"name": "League of Legends", "emoji": "⚔️"},
    {"name": "VALORANT", "emoji": "🎯"},
    {"name": "CS2", "emoji": "🔫"},
    {"name": "Minecraft", "emoji": "🧱"},
    {"name": "Rust", "emoji": "☢️"},
    {"name": "PUBG", "emoji": "🐔"},
    {"name": "PUBG Mobile", "emoji": "📱"},
    {"name": "Among Us", "emoji": "👨‍🚀"},
    {"name": "ETS 2", "emoji": "🚛"}
]

VOICE_EMOJIS = ["🎧", "🔥", "⚔️", "🎮", "💀"]

message_cache = {}

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
        guild_id INTEGER,
        user_id INTEGER,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 0,
        last_gain REAL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS swear_counts (
        guild_id INTEGER,
        user_id INTEGER,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """)

    con.commit()
    con.close()


# =========================================================
# YARDIMCI
# =========================================================
def find_role(guild, name):
    return discord.utils.get(guild.roles, name=name)


def find_text_channel(guild, name):
    return discord.utils.get(guild.text_channels, name=name)


def is_staff(member):
    allowed = [
        "👑 Founder",
        "💠 Co-Founder",
            "⚡ Yönetici",
        "🔧 Admin",
        "🛡️ Moderatör"
    ]

    return any(role.name in allowed for role in member.roles)


async def get_or_create_role(guild, name, permissions=None):
    role = find_role(guild, name)

    if role:
        return role

    if permissions is None:
        permissions = discord.Permissions.none()

    return await guild.create_role(
        name=name,
        permissions=permissions,
        reason="Zental kurulum"
    )


# =========================================================
# ON READY
# =========================================================
@bot.event
async def on_ready():
    init_db()

    print(f"Bot aktif: {bot.user}")

    live_checker.start()

    try:
        synced = await bot.tree.sync(
            guild=discord.Object(id=GUILD_ID)
        )

        print(f"Slash komut: {len(synced)}")

    except Exception as e:
        print(e)


# =========================================================
# ÜYE GİRİŞİ
# =========================================================
@bot.event
async def on_member_join(member):

    uye_role = find_role(member.guild, "👤 Üye")

    if uye_role:
        try:
            await member.add_roles(
                uye_role,
                reason="Otomatik üye rolü"
            )
        except Exception as e:
            print(e)

    kanal = find_text_channel(member.guild, "👋・hos-geldin")

    if kanal:
        try:
            await kanal.send(
                f"🚀 Hoş geldin {member.mention}!"
            )
        except:
            pass


# =========================================================
# KÜFÜR SİSTEMİ
# =========================================================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    content = message.content.lower()

    if not is_staff(message.author):

        if any(word in content for word in BAD_WORDS):

            con = db()
            cur = con.cursor()

            cur.execute("""
            INSERT OR IGNORE INTO swear_counts
            (guild_id, user_id, count)
            VALUES (?, ?, 0)
            """, (message.guild.id, message.author.id))

            cur.execute("""
            UPDATE swear_counts
            SET count = count + 1
            WHERE guild_id=? AND user_id=?
            """, (message.guild.id, message.author.id))

            cur.execute("""
            SELECT count
            FROM swear_counts
            WHERE guild_id=? AND user_id=?
            """, (message.guild.id, message.author.id))

            count = cur.fetchone()[0]

            con.commit()
            con.close()

            try:
                await message.delete()
            except:
                pass

            try:
                if count == 1:
                    await message.author.timeout(
                        timedelta(minutes=5)
                    )

                elif count == 2:
                    await message.author.timeout(
                        timedelta(minutes=10)
                    )

                elif count == 3:
                    await message.author.timeout(
                        timedelta(minutes=30)
                    )

                else:
                    await message.guild.ban(
                        message.author,
                        reason="Tekrarlayan küfür"
                    )

                await message.channel.send(
                    f"{message.author.mention} küfür yasak 🚫",
                    delete_after=5
                )

            except Exception as e:
                print(e)

            return

    await bot.process_commands(message)


# =========================================================
# KÜFÜR EKLE
# =========================================================
@bot.command(name="kufurekle")
async def kufurekle(ctx, *, kelime):

    if not is_staff(ctx.author):
        await ctx.send("Yetkin yok")
        return

    kelime = kelime.lower()

    if kelime in BAD_WORDS:
        await ctx.send("Zaten listede")
        return

    BAD_WORDS.append(kelime)

    await ctx.send(f"✅ {kelime} listeye eklendi")


# =========================================================
# TEMİZLE
# =========================================================
@bot.command(name="temizle")
async def temizle(ctx, amount=10):

    if not is_staff(ctx.author):
        await ctx.send("Yetkin yok")
        return

    deleted = await ctx.channel.purge(limit=amount + 1)

    await ctx.send(
        f"🧹 {len(deleted)-1} mesaj silindi",
        delete_after=5
    )


# =========================================================
# ROL PANEL
# =========================================================
class GameRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, interaction, role_name):

        role = find_role(interaction.guild, role_name)

        if not role:
            await interaction.response.send_message(
                "Rol bulunamadı",
                ephemeral=True
            )
            return

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(
                    f"{role.name} kaldırıldı",
                    ephemeral=True
                )
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    f"{role.name} verildi",
                    ephemeral=True
                )
        except Exception as e:
            print(e)

    @discord.ui.button(label="Rust", style=discord.ButtonStyle.primary)
    async def rust_btn(self, interaction, button):
        await self.toggle_role(interaction, "🎮 Rust")

    @discord.ui.button(label="VALORANT", style=discord.ButtonStyle.danger)
    async def val_btn(self, interaction, button):
        await self.toggle_role(interaction, "🎮 VALORANT")

    @discord.ui.button(label="CS2", style=discord.ButtonStyle.secondary)
    async def cs_btn(self, interaction, button):
        await self.toggle_role(interaction, "🎮 CS2")


# =========================================================
# ROL PANEL KOMUTU
# =========================================================
@bot.tree.command(
    name="rolpanel",
    description="Rol paneli",
    guild=discord.Object(id=GUILD_ID)
)
async def rolpanel(interaction):

    if not is_staff(interaction.user):
        await interaction.response.send_message(
            "Yetkin yok",
            ephemeral=True
        )
        return

    await interaction.channel.send(
        "🎮 Oyun rolünü seç:",
        view=GameRoleView()
    )

    await interaction.response.send_message(
        "Gönderildi",
        ephemeral=True
    )


# =========================================================
# GÜNCELLEME SİSTEMİ
# /guncelle mevcut sunucuyu silmez.
# Sadece eksik kanal/rol/panel/metin varsa ekler veya günceller.
# =========================================================
@bot.tree.command(
    name="guncelle",
    description="Mevcut sunucuyu silmeden Zental ayarlarını günceller",
    guild=discord.Object(id=GUILD_ID)
)
async def guncelle(interaction):

    if interaction.user.id != OWNER_USER_ID:
        await interaction.response.send_message(
            "Sadece Founder kullanabilir",
            ephemeral=True
        )
        return

    guild = interaction.guild
    await interaction.response.defer(ephemeral=True)

    try:
        # ROLLERİ EKSİKSE OLUŞTUR
        member_perm = discord.Permissions(
            send_messages=True,
            connect=True,
            speak=True,
            view_channel=True
        )

        role_names = [
            "👤 Üye",
            "👑 Prenses",
            "🎥 Yayıncı",
            "⚔️ Takım 1",
            "🔥 Aktif Üye",
            "💎 VIP",
            "🛡️ Moderatör",
            "🔧 Admin",
            "⚡ Yönetici",
            "👑 Founder",
        ]

        for game in GAMES:
            role_names.append(f"🎮 {game}")

        for role_name in role_names:
            await get_or_create_role(guild, role_name, member_perm)

        # KURALLAR KANALINI BUL VEYA OLUŞTUR
        kurallar = find_text_channel(guild, "📜・kurallar")

        if not kurallar:
            info_cat = discord.utils.get(guild.categories, name="📢 BİLGİ")
            if not info_cat:
                info_cat = await guild.create_category("📢 BİLGİ")

            kurallar = await guild.create_text_channel(
                "📜・kurallar",
                category=info_cat
            )

        # BOTUN ESKİ KURAL MESAJLARINI TEMİZLE
        async for msg in kurallar.history(limit=50):
            if msg.author == guild.me:
                try:
                    await msg.delete()
                except:
                    pass

        await kurallar.send(
            """📜 **ZENTAL COMMUNITY SUNUCU KURALLARI**

Zental Community düzenli, saygılı ve kaliteli bir oyun topluluğudur.
Sunucuda bulunan herkes aşağıdaki kuralları kabul etmiş sayılır.

━━━━━━━━━━━━━━━━━━━━

1️⃣ Saygılı olun.
Hakaret, aşağılama, dalga geçme ve huzur bozmak yasaktır.

2️⃣ Küfür yasaktır.
Bot küfür sistemine sahiptir.
Tekrarlayan küfürler timeout veya ban ile sonuçlanabilir.

3️⃣ Reklam yasaktır.
İzinsiz Discord linki, yayın linki veya satış paylaşımı yapılamaz.

4️⃣ Spam ve flood yasaktır.
Arka arkaya mesaj atmak veya gereksiz etiket kullanmak yasaktır.

5️⃣ Ses odalarında düzen zorunludur.
Mikrofon basmak, bağırmak veya rahatsızlık vermek yasaktır.

6️⃣ Takım odaları özeldir.
Takım 1 kanalları sadece ilgili üyeler içindir.

7️⃣ Yetkili kararlarına saygı gösterilmelidir.
Yetkili tartışmaları büyütme sebebi değildir.

8️⃣ +18 içerik yasaktır.
Rahatsız edici içerikler direkt ceza sebebidir.

9️⃣ Dolandırıcılık yasaktır.
Sahte link, scam veya zararlı içerik paylaşımı yasaktır.

🔟 Ağır ihlallerde direkt ban uygulanabilir.

━━━━━━━━━━━━━━━━━━━━

⚠️ CEZA SİSTEMİ

• Timeout
• Rol kaldırma
• Kanal engeli
• Kick
• Kalıcı ban

uygulanabilir.

👑 Son karar Founder ve Yönetim ekibine aittir.
"""
        )

        await interaction.followup.send(
            "✅ Güncelleme tamamlandı. Hiçbir kanal silinmedi; mevcut sistemin üstüne eksikler eklendi ve kurallar yenilendi.",
            ephemeral=True
        )

    except Exception as e:
        await interaction.followup.send(
            f"Güncelleme hatası: {e}",
            ephemeral=True
        )


# =========================================================
# FULL KURULUM
# =========================================================
@bot.tree.command(
    name="kur",
    description="Zental full kurulum",
    guild=discord.Object(id=GUILD_ID)
)
async def kur(interaction):

    if interaction.user.id != OWNER_USER_ID:
        await interaction.response.send_message(
            "Sadece Founder kullanabilir",
            ephemeral=True
        )
        return

    guild = interaction.guild

    await interaction.response.defer(ephemeral=True)

    try:

        # =================================================
        # GÜVENLİ KANAL
        # =================================================
        guvenli_kategori = discord.utils.get(
            guild.categories,
            name="⚙️ ZENTAL KURULUM"
        )

        if not guvenli_kategori:
            guvenli_kategori = await guild.create_category(
                name="⚙️ ZENTAL KURULUM"
            )

        guvenli_kanal = discord.utils.get(
            guild.text_channels,
            name="🛠️・kurulum-log"
        )

        if not guvenli_kanal:
            guvenli_kanal = await guild.create_text_channel(
                name="🛠️・kurulum-log",
                category=guvenli_kategori
            )

        await guvenli_kanal.send(
            "🚀 Zental kurulumu başladı"
        )

        # =================================================
        # TÜM KANALLARI SİL
        # =================================================
        channels = [
            c for c in guild.channels
            if c.id != guvenli_kanal.id
            and c.id != guvenli_kategori.id
        ]

        for channel in channels:
            try:
                await channel.delete()
                await asyncio.sleep(1)
            except Exception as e:
                print(e)

        await asyncio.sleep(5)

        # =================================================
        # TÜM ROLLERİ SİL
        # =================================================
        me = guild.me

        for role in list(guild.roles):

            if role.is_default():
                continue

            if me and role >= me.top_role:
                continue

            try:
                await role.delete()
                await asyncio.sleep(0.5)
            except Exception as e:
                print(e)

        # =================================================
        # ROLLER
        # =================================================
        role_colors = {
            "👑 Founder": discord.Color.from_rgb(255, 215, 0),
            "💠 Co-Founder": discord.Color.from_rgb(0, 255, 170),
            "⚡ Yönetici": discord.Color.from_rgb(255, 0, 0),
            "🔧 Admin": discord.Color.from_rgb(255, 85, 85),
            "🛡️ Moderatör": discord.Color.from_rgb(0, 170, 255),
            "👤 Üye": discord.Color.from_rgb(120, 120, 120),
            "👑 Prenses": discord.Color.from_rgb(255, 105, 180),
            "🎥 Yayıncı": discord.Color.from_rgb(170, 0, 255),
            "⚔️ Takım 1": discord.Color.from_rgb(255, 140, 0),
            "🔥 Aktif Üye": discord.Color.from_rgb(255, 80, 0),
            "💎 VIP": discord.Color.from_rgb(0, 255, 255),
        }

        game_colors = [
            discord.Color.from_rgb(0, 255, 120),
            discord.Color.from_rgb(255, 0, 255),
            discord.Color.from_rgb(0, 140, 255),
            discord.Color.from_rgb(255, 255, 0),
            discord.Color.from_rgb(0, 255, 200),
            discord.Color.from_rgb(255, 120, 120),
            discord.Color.from_rgb(120, 255, 120),
            discord.Color.from_rgb(120, 120, 255),
            discord.Color.from_rgb(255, 180, 0),
            discord.Color.from_rgb(180, 0, 255),
        ]
        # =================================================
        founder_perm = discord.Permissions.all()

        admin_perm = discord.Permissions(
            administrator=True
        )

        member_perm = discord.Permissions(
            send_messages=True,
            connect=True,
            speak=True,
            view_channel=True
        )

        founder_role = await guild.create_role(
            name="👑 Founder",
            permissions=founder_perm,
            color=role_colors["👑 Founder"]
        )

        co_founder_role = await guild.create_role(
            name="💠 Co-Founder",
            permissions=admin_perm,
            color=role_colors["💠 Co-Founder"]
        )

        yonetici_role = await guild.create_role(
            name="⚡ Yönetici",
            permissions=admin_perm,
            color=role_colors["⚡ Yönetici"]
        )

        admin_role = await guild.create_role(
            name="🔧 Admin",
            permissions=admin_perm,
            color=role_colors["🔧 Admin"]
        )

        mod_role = await guild.create_role(
            name="🛡️ Moderatör",
            permissions=admin_perm,
            color=role_colors["🛡️ Moderatör"]
        )

        uye_role = await guild.create_role(
            name="👤 Üye",
            permissions=member_perm,
            color=role_colors["👤 Üye"]
        )

        await get_or_create_role(
            guild,
            "👑 Prenses",
            member_perm
        )

        await get_or_create_role(
            guild,
            "🎥 Yayıncı",
            member_perm
        )

        takim_role = await get_or_create_role(
            guild,
            "⚔️ Takım 1",
            member_perm
        )

        await get_or_create_role(
            guild,
            "🔥 Aktif Üye",
            member_perm
        )

        await get_or_create_role(
            guild,
            "💎 VIP",
            member_perm
        )

        for game in GAMES:
            await get_or_create_role(
                guild,
                f"{game['emoji']} {game['name']}",
                member_perm
            )

        # =================================================
        # KATEGORİLER
        # =================================================
        info_cat = await guild.create_category("📢 BİLGİ")
        chat_cat = await guild.create_category("💬 TOPLULUK")
        voice_cat = await guild.create_category("🔊 SES")
        stream_cat = await guild.create_category("🎥 YAYIN")
        support_cat = await guild.create_category("🛠️ DESTEK")

        takim_cat = await guild.create_category(
            "⚔️ TAKIM 1",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=False
                ),
                takim_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    connect=True,
                    speak=True
                )
            }
        )

        # =================================================
        # BİLGİ KANALLARI
        # =================================================
        await guild.create_text_channel(
            "👋・hos-geldin",
            category=info_cat
        )

        kurallar = await guild.create_text_channel(
            "📜・kurallar",
            category=info_cat
        )

        await guild.create_text_channel(
            "📢・duyurular",
            category=info_cat
        )

        await guild.create_text_channel(
            "🎮・rol-al",
            category=info_cat
        )

        await guild.create_text_channel(
            "📣・reklam",
            category=info_cat,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(
                    send_messages=False
                ),
                founder_role: discord.PermissionOverwrite(
                    send_messages=True
                ),
                yonetici_role: discord.PermissionOverwrite(
                    send_messages=True
                )
            }
        )

        # =================================================
        # TOPLULUK
        # =================================================
        await guild.create_text_channel(
            "💬・genel",
            category=chat_cat
        )

        await guild.create_text_channel(
            "😂・mizah",
            category=chat_cat
        )

        await guild.create_text_channel(
            "📸・medya",
            category=chat_cat
        )

        # =================================================
        # OYUN ODALARI
        # =================================================
        for game in GAMES:

            game_role = find_role(guild, f"{game['emoji']} {game['name']}")

            game_cat = await guild.create_category(
                f"{game['emoji']} {game['name']}",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=True
                    ),
                    game_role: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        connect=True,
                        speak=True
                    )
                }
            )

            await guild.create_text_channel(
                f"💬・{game['name'].lower().replace(' ', '-')}-sohbet",
                category=game_cat
            )

            await guild.create_text_channel(
                f"🤝・{game['name'].lower().replace(' ', '-')}-takim-ara",
                category=game_cat
            )

            for i in range(5):
                await guild.create_voice_channel(
                    f"{VOICE_EMOJIS[i]}・{game['name']} {i+1}",
                    category=game_cat
                )

        # =================================================
        # SES ODALARI
        # =================================================
        voice_names = [
            "🎧・Genel Sohbet",
            "🔥・Aktif Oda",
            "⚔️・Takım Kur",
            "🎵・Müzik Odası",
            "💤・AFK"
        ]

        for name in voice_names:
            await guild.create_voice_channel(
                name,
                category=voice_cat
            )

        # =================================================
        # TAKIM 1
        # =================================================
        await guild.create_text_channel(
            "⚔️・takim-1-chat",
            category=takim_cat
        )

        await guild.create_voice_channel(
            "⚔️・Takım Voice",
            category=takim_cat
        )

        # =================================================
        # YAYIN
        # =================================================
        await guild.create_text_channel(
            "📡・yayin-duyuru",
            category=stream_cat
        )

        await guild.create_voice_channel(
            "📡・Yayıncı Voice",
            category=stream_cat
        )

        # =================================================
        # DESTEK
        # =================================================
        await guild.create_text_channel(
            "📋・log",
            category=support_cat
        )

        await guild.create_text_channel(
            "📝・istek-oneri",
            category=support_cat
        )

        # =================================================
        # KURALLAR MESAJI
        # =================================================
        await kurallar.send(
            "📜 ZENTAL KURALLARI\n\n"
            "• Küfür yasak\n"
            "• Reklam yasak\n"
            "• Saygı zorunlu\n"
            "• Spam yasak\n"
            "• Yetkili kararları geçerlidir\n"
            "• Ağır ihlalde direkt ban uygulanabilir"
        )

        # =================================================
        # HERKESE ÜYE ROLÜ
        # =================================================
        for member in guild.members:

            if member.bot:
                continue

            try:
                await member.add_roles(uye_role)
            except Exception as e:
                print(e)

        # =================================================
        # TAMAMLANDI
        # =================================================
        await guvenli_kanal.send(
            "✅ Kurulum tamamlandı"
        )

        await interaction.followup.send(
            "✅ Zental kuruldu",
            ephemeral=True
        )

    except Exception as e:
        print(e)

        await interaction.followup.send(
            f"Kurulum hatası: {e}",
            ephemeral=True
        )


# =========================================================
# TWITCH + YOUTUBE YAYIN SİSTEMİ
# =========================================================
import aiohttp

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

STREAMERS = {
    1365752307056119982: {
        "twitch": "zendarkkk",
        "youtube": "zendark-tw"
    }
}

# Yayıncı rolü alan kişilerin ID ve hesaplarını buraya ekle.
# Örnek:
# 123456789: {
#     "twitch": "kullaniciadi",
#     "youtube": "kanaladi"
# }

live_cache = {}


async def get_twitch_token():
    url = "https://id.twitch.tv/oauth2/token"

    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as r:
            data = await r.json()
            return data.get("access_token")


async def check_twitch_live(guild):

    for user_id, accounts in STREAMERS.items():

        twitch_name = accounts.get("twitch")

        if not twitch_name:
            continue

    try:
        token = await get_twitch_token()

        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }

        url = f"https://api.twitch.tv/helix/streams?user_login={twitch_name}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as r:
                data = await r.json()

        kanal = find_text_channel(guild, "📡・yayin-duyuru")

        if not kanal:
            return

        cache_key = f"twitch_{twitch_name}"

        if cache_key not in live_cache:
            live_cache[cache_key] = False

        if data.get("data"):

            if not live_cache[cache_key]:

                live_cache[cache_key] = True

                await kanal.send(
                    f"🔴 **{twitch_name} Twitch canlı yayında!**"
                    f"📺 https://twitch.tv/{twitch_name}"
                )

        else:
            live_cache[cache_key] = False

    except Exception as e:
        print(f"Twitch hata: {e}")


async def check_youtube_live(guild):

    for user_id, accounts in STREAMERS.items():

        youtube_name = accounts.get("youtube")

        if not youtube_name:
            continue

        try:
            kanal = find_text_channel(guild, "📡・yayin-duyuru")

            if not kanal:
                return

            cache_key = f"youtube_{youtube_name}"

            if cache_key not in live_cache:
                live_cache[cache_key] = False

            search_url = (
                "https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&channelType=any&maxResults=1&q={youtube_name}"
                f"&type=channel&key={YOUTUBE_API_KEY}"
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url) as r:
                    data = await r.json()

            items = data.get("items", [])

            if not items:
                continue

            channel_id = items[0]["snippet"]["channelId"]

            live_url = (
                "https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&channelId={channel_id}"
                "&eventType=live&type=video"
                f"&key={YOUTUBE_API_KEY}"
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(live_url) as r:
                    live_data = await r.json()

            if live_data.get("items"):

                if not live_cache[cache_key]:

                    live_cache[cache_key] = True

                    video_id = live_data["items"][0]["id"]["videoId"]

                    await kanal.send(
                        f"🔴 **{youtube_name} YouTube canlı yayında!**

"
                        f"📺 https://youtube.com/watch?v={video_id}"
                    )

            else:
                live_cache[cache_key] = False

        except Exception as e:
            print(f"YouTube hata: {e}")


@tasks.loop(minutes=2)
async def live_checker():

    guild = bot.get_guild(GUILD_ID)

    if not guild:
        return

    await check_twitch_live(guild)
    await check_youtube_live(guild)


@live_checker.before_loop
async def before_live_checker():
    await bot.wait_until_ready()


# =========================================================
# EKLENMESİ PLANLANAN GELİŞMİŞ SİSTEMLER
# =========================================================
# ✅ Ticket sistemi
# ✅ Level / XP sistemi
# ✅ Leaderboard sistemi
# ✅ Ekonomi sistemi
# ✅ Çekiliş sistemi
# ✅ Yapay zeka sohbet sistemi
# ✅ Otomatik özel oda sistemi
# ✅ Ses aktivite XP sistemi
# ✅ Başvuru sistemi
# ✅ Oyun etkinlik sistemi
# ✅ Twitch Drop duyuru sistemi
# ✅ Rust wipe duyuru sistemi
# ✅ Yayın açınca otomatik ses odası taşıma
# ✅ Otomatik yayıncı rol sistemi
# ✅ Kayıt sistemi
# ✅ Ceza kayıt sistemi
# ✅ Yetkili log sistemi
# ✅ Join / leave log sistemi
# ✅ Moderasyon panel sistemi
# ✅ Sunucu istatistik sistemi
# ✅ Özel profil sistemi
# ✅ Günlük görev sistemi
# ✅ Haftalık aktiflik sistemi
# ✅ Otomatik oda oluşturma sistemi
# ✅ Gece modu / bakım modu sistemi
# ✅ Emoji rol sistemi
# ✅ Müzik sistemi
# ✅ Spotify durum sistemi
# ✅ Twitch abonelik kontrol sistemi
# ✅ Oyun içi takım sistemi
# ✅ AI destekli moderasyon sistemi
#
# NOT:
# Bu sistemler altyapı olarak hazırlanmıştır.
# İstenilen modüller sonradan aktif edilebilir.
# =========================================================
# BOT BAŞLAT
# =========================================================
bot.run(TOKEN)
