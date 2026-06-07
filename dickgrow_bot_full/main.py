import os, sqlite3, random, time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto

TOKEN = os.getenv("BOT_TOKEN")
DB="database.db"
COOLDOWN=1*60*60
ADMIN_ID=5952134460

db=sqlite3.connect(DB)
c=db.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,name TEXT,size INTEGER DEFAULT 0,debt INTEGER DEFAULT 0,last_grow INTEGER DEFAULT 0)")
c.execute("CREATE TABLE IF NOT EXISTS battles(id INTEGER PRIMARY KEY AUTOINCREMENT,creator INTEGER,bet INTEGER,active INTEGER DEFAULT 1)")
c.execute("CREATE TABLE IF NOT EXISTS loans(lender_id INTEGER, borrower_id INTEGER, amount INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, celeb TEXT, price INTEGER, active INTEGER DEFAULT 1)")
db.commit()

def user(uid,name):
    c.execute("INSERT OR IGNORE INTO users(user_id,name) VALUES(?,?)",(uid,name))
    c.execute("UPDATE users SET name=? WHERE user_id=?",(name,uid))
    db.commit()

dp=Dispatcher()

@dp.message(Command("grow"))
async def grow(m:Message):
    user(m.from_user.id,m.from_user.full_name)
    size,last=c.execute("SELECT size,last_grow FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()
    now=int(time.time())
    if now-last<COOLDOWN:
        rem=(COOLDOWN-(now-last))//60
        return await m.reply(f"⏳ هنوز {rem} دقیقه تا رشد بعدی مونده!")
    delta=random.randint(5,20) 
    size=max(0,size+delta)
    c.execute("UPDATE users SET size=?,last_grow=? WHERE user_id=?",(size,now,m.from_user.id)); db.commit()
    await m.reply(
        f"🌱 نتیجه رشد\n\n🍆 تغییر: {delta:+} سانت\n📏 اندازه فعلی: {size} سانت\n😎 ادامه بده قهرمان!"
    )

@dp.message(Command("size"))
async def size(m:Message):
    user(m.from_user.id,m.from_user.full_name)
    s,d=c.execute("SELECT size,debt FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()
    await m.reply(
        f"📊 پروفایل شما\n\n🍆 اندازه: {s} سانت\n💸 بدهی: {d} سانت"
    )

@dp.message(Command("loan"))
async def loan(m:Message):
    try:
        amt=int(m.text.split()[1])
    except:
        return await m.reply("Reply to a user and use /loan 5")

    if not m.reply_to_message:
        return await m.reply("Reply to a user and use /loan 5")

    lender=m.from_user.id
    borrower=m.reply_to_message.from_user.id

    if lender==borrower:
        return await m.reply("You can't loan yourself.")

    user(lender,m.from_user.full_name)
    user(borrower,m.reply_to_message.from_user.full_name)

    s=c.execute("SELECT size FROM users WHERE user_id=?",(lender,)).fetchone()[0]

    if s<amt:
        return await m.reply("Not enough cm.")

    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(amt,lender))
    c.execute("UPDATE users SET size=size+? WHERE user_id=?",(amt,borrower))
    c.execute("INSERT INTO loans VALUES(?,?,?)",(lender,borrower,amt))
    db.commit()

    await m.reply(f"💸 وام انجام شد!\n\nمقدار: {amt} سانت")

@dp.message(Command("repay"))
async def repay(m:Message):
    try: amt=int(m.text.split()[1])
    except: return await m.reply("Usage: /repay 5")
    user(m.from_user.id,m.from_user.full_name)
    s,d=c.execute("SELECT size,debt FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()
    amt=min(amt,s,d)
    c.execute("UPDATE users SET size=?,debt=? WHERE user_id=?",(s-amt,d-amt,m.from_user.id)); db.commit()
    await m.reply(f"✅ Repaid {amt} cm")

@dp.message(Command("top"))
async def top(m:Message):
    rows=c.execute("SELECT name,size FROM users ORDER BY size DESC LIMIT 10").fetchall()
    txt="🏆 جدول بزرگان\n\n"
    for i,(n,s) in enumerate(rows,1): txt+=f"{i}. {n} — {s} سانت\n"
    await m.reply(txt)

@dp.message(Command("pvp"))
async def pvp(m:Message):
    try: bet=int(m.text.split()[1])
    except: return await m.reply("Usage: /pvp 30")
    user(m.from_user.id,m.from_user.full_name)
    s=c.execute("SELECT size FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()[0]
    if s<bet: return await m.reply("Not enough cm.")
    cur = c.execute(
        "INSERT INTO battles(creator,bet) VALUES(?,?)",
        (m.from_user.id, bet)
    )
    db.commit()
    bid=cur.lastrowid
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚔️ قبول دوئل",callback_data=f"pvp:{bid}")]])
    await m.reply(f"⚔️ دوئل مرگبار!\n\n💰 شرط: {bet} سانت\n\nبرنده همه رو می‌بره!",reply_markup=kb)

@dp.callback_query(F.data.startswith("pvp:"))
async def accept(q:CallbackQuery):
    bid=int(q.data.split(":")[1])
    row=c.execute("SELECT creator,bet,active FROM battles WHERE id=?",(bid,)).fetchone()
    if not row or row[2]==0: return await q.answer("Expired")
    creator,bet,_=row
    if q.from_user.id==creator: return await q.answer("Not yourself")
    user(q.from_user.id,q.from_user.full_name)
    s1=c.execute("SELECT size FROM users WHERE user_id=?",(creator,)).fetchone()[0]
    s2=c.execute("SELECT size FROM users WHERE user_id=?",(q.from_user.id,)).fetchone()[0]
    if s1<bet or s2<bet: return await q.answer("Not enough cm")
    winner=random.choice([creator,q.from_user.id])
    loser=q.from_user.id if winner==creator else creator
    c.execute("UPDATE users SET size=size+? WHERE user_id=?",(bet,winner))
    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(bet,loser))
    c.execute("UPDATE battles SET active=0 WHERE id=?",(bid,))
    db.commit()
    winner_name=c.execute("SELECT name FROM users WHERE user_id=?",(winner,)).fetchone()[0]
    await q.message.edit_text(f"🏆 پایان دوئل!\n\n👑 برنده: {winner_name}\n💰 جایزه: {bet} سانت\n\n😂 بازنده باید بیشتر تمرین کنه!")


# ===== Celebrity Collection System =====
c.execute("CREATE TABLE IF NOT EXISTS collections(user_id INTEGER, celeb TEXT, paid_price INTEGER DEFAULT 0)")
db.commit()


CELEBS = {
    "Ana de Armas": ("S",300,150,"https://i.postimg.cc/5037v189/photo-5848289682741988825-x.jpg"),
    "Madison Beer": ("S",300,150,"https://i.postimg.cc/c4Dp27g8/photo-5848289682741988827-x.jpg"),
    "Georgina Rodriguez": ("S",300,150,"https://i.postimg.cc/J4hgNyT6/photo-5848289682741988826-x.jpg"),
    "Kylie Jenner": ("S",300,150,"https://i.postimg.cc/XYYVy7Fw/photo-5848328955922944688-x.jpg"),
    "Sydney Sweeney": ("S",300,150,"https://i.postimg.cc/zfw0Z5tP/photo-5848289682741988820-y.jpg"),
    "Olivia Cooke": ("A",200,100,"https://i.postimg.cc/t4Q3XwVN/photo-5848289682741988811-y.jpg"),
    "Scarlett Johansson": ("A",200,100,"https://i.postimg.cc/9f2YBKmW/photo-5848289682741988817-y.jpg"),
    "Sabrina Carpenter": ("A",200,100,"https://i.postimg.cc/L6hCqc56/photo-5848289682741988822-x.jpg"),
    "Olivia Rodrigo": ("A",200,100,"https://i.postimg.cc/jS1rw6tv/photo-5848289682741988828-y.jpg"),
    "Kendall Jenner": ("A",200,100,"https://i.postimg.cc/Yqp7Jqdb/photo-5848289682741988829-y.jpg"),
    "Kathryn Newton": ("B",100,50,"https://i.postimg.cc/J08ywVFN/Kathryn-Newton-4DX-2023.jpg"),
    "Margot Robbie": ("B",100,50,"https://i.postimg.cc/rFmVDw59/b4965bcbfbe0e83ad658b74fa2c57cd0.jpg"),
    "Taylor Swift": ("B",100,50,"https://i.postimg.cc/JhWC5rHq/images.jpg"),
    "Dua Lipa": ("B",100,50,"https://i.postimg.cc/Fz62dNQS/Dua-Lipa-with-Warner-Music.jpg"),
    "Megan Fox": ("B",100,50,"https://i.postimg.cc/W4VxJ5xg/Megan-Fox.jpg"),
}


TIER_CELEBS = {
    "S": [(n, v[1], v[3]) for n, v in CELEBS.items() if v[0] == "S"],
    "A": [(n, v[1], v[3]) for n, v in CELEBS.items() if v[0] == "A"],
    "B": [(n, v[1], v[3]) for n, v in CELEBS.items() if v[0] == "B"],
}
TIER_LABELS = {
    "S": "🥇 Tier S",
    "A": "🥈 Tier A",
    "B": "🥉 Tier B",
}
TIER_PRICES = {"S": (300, 150), "A": (200, 100), "B": (100, 50)}

def build_market_caption(tier, page):
    celebs = TIER_CELEBS[tier]
    name, price, photo = celebs[page]
    buy_price, spin_price = TIER_PRICES[tier]
    label = TIER_LABELS[tier]
    txt = (
        f"🛒 بازار سلبریتی\n"
        f"{label} — صفحه {page+1}/{len(celebs)}\n\n"
        f"👑 {name}\n"
        f"💰 خرید: {price} سانت\n"
        f"🎰 اسپین: {spin_price} سانت\n\n"
        f"🛒 /buy {name}\n"
        f"🎰 /spin {tier.lower()}"
    )
    return txt, photo

def build_market_kb(tier, page):
    celebs = TIER_CELEBS[tier]
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"mkt:{tier}:{page-1}"))
    if page < len(celebs) - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"mkt:{tier}:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

@dp.message(Command("market"))
async def market(m:Message):
    for tier in ["S", "A", "B"]:
        txt, photo = build_market_caption(tier, 0)
        kb = build_market_kb(tier, 0)
        try:
            await m.bot.send_photo(m.chat.id, photo, caption=txt, reply_markup=kb)
        except Exception:
            await m.bot.send_message(m.chat.id, txt, reply_markup=kb)

@dp.callback_query(F.data.startswith("mkt:"))
async def market_page_nav(q: CallbackQuery):
    _, tier, page = q.data.split(":")
    page = int(page)
    txt, photo = build_market_caption(tier, page)
    kb = build_market_kb(tier, page)
    try:
        await q.message.edit_media(
            media=InputMediaPhoto(media=photo, caption=txt),
            reply_markup=kb
        )
    except Exception:
        try:
            await q.message.edit_caption(caption=txt, reply_markup=kb)
        except Exception:
            await q.message.answer(txt, reply_markup=kb)
    await q.answer()

@dp.message(Command("collection"))
async def collection(m:Message):
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        user(target.id, target.full_name)
        rows = c.execute("SELECT celeb FROM collections WHERE user_id=?", (target.id,)).fetchall()
        if not rows:
            return await m.reply(f"📚 {target.full_name} هنوز چیزی نداره.")
        celebs = [r[0] for r in rows]
        await send_collection_page(m.chat.id, target.id, celebs, 0, m.bot, viewer_id=m.from_user.id)
    else:
        user(m.from_user.id, m.from_user.full_name)
        rows = c.execute("SELECT celeb FROM collections WHERE user_id=?", (m.from_user.id,)).fetchall()
        if not rows:
            return await m.reply("📚 هنوز چیزی نداری.")
        celebs = [r[0] for r in rows]
        await send_collection_page(m.chat.id, m.from_user.id, celebs, 0, m.bot, viewer_id=m.from_user.id)

async def send_collection_page(chat_id, owner_id, celebs, page, bot, viewer_id=None):
    name = celebs[page]
    tier, price, spin, photo = CELEBS[name]
    tier_label = {"S": "🥇 S", "A": "🥈 A", "B": "🥉 B"}[tier]
    txt = (
        f"📚 کالکشن — {page+1}/{len(celebs)}\n\n"
        f"👑 {name}\n"
        f"🏅 تیر: {tier_label}\n"
        f"💰 ارزش: {price} سانت\n\n"
        f"🛒 /sell {name}\n"
        f"🏪 /list {name} [قیمت]"
    )
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"col:{owner_id}:{page-1}"))
    if page < len(celebs) - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"col:{owner_id}:{page+1}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
    if photo:
        try:
            await bot.send_photo(chat_id, photo, caption=txt, reply_markup=kb)
            return
        except:
            pass
    await bot.send_message(chat_id, txt, reply_markup=kb)

@dp.callback_query(F.data.startswith("col:"))
async def collection_nav(q: CallbackQuery):
    _, owner_id, page = q.data.split(":")
    owner_id = int(owner_id)
    page = int(page)
    # allow anyone to browse
    rows = c.execute("SELECT celeb FROM collections WHERE user_id=?", (owner_id,)).fetchall()
    celebs = [r[0] for r in rows]
    if page >= len(celebs):
        page = len(celebs) - 1
    name = celebs[page]
    tier, price, spin, photo = CELEBS[name]
    tier_label = {"S": "🥇 S", "A": "🥈 A", "B": "🥉 B"}[tier]
    txt = (
        f"📚 کالکشن — {page+1}/{len(celebs)}\n\n"
        f"👑 {name}\n"
        f"🏅 تیر: {tier_label}\n"
        f"💰 ارزش: {price} سانت\n\n"
        f"🛒 /sell {name}\n"
        f"🏪 /list {name} [قیمت]"
    )
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"col:{owner_id}:{page-1}"))
    if page < len(celebs) - 1:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"col:{owner_id}:{page+1}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
    try:
        if photo:
            await q.message.edit_media(
                media=InputMediaPhoto(media=photo, caption=txt),
                reply_markup=kb
            )
        else:
            await q.message.edit_caption(caption=txt, reply_markup=kb)
    except Exception:
        await q.message.answer(txt, reply_markup=kb)
    await q.answer()


@dp.message(Command("buy"))
async def buy(m:Message):
    name=m.text.replace("/buy","",1).strip()

    if name not in CELEBS:
        return await m.reply("❌ سلبریتی پیدا نشد.")

    tier,price,spin,photo=CELEBS[name]

    user(m.from_user.id,m.from_user.full_name)

    size=c.execute("SELECT size FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()[0]

    if size<price:
        return await m.reply("💸 سانت کافی نداری!")

    owned=c.execute(
        "SELECT user_id FROM collections WHERE celeb=?",
        (name,)
    ).fetchone()

    if owned:
        if owned[0] == m.from_user.id:
            return await m.reply("📚 این سلبریتی رو داری!")
        owner_name=c.execute("SELECT name FROM users WHERE user_id=?",(owned[0],)).fetchone()[0]
        return await m.reply(f"❌ این سلبریتی قبلاً توسط {owner_name} خریداری شده!")

    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(price,m.from_user.id))
    c.execute("INSERT INTO collections(user_id,celeb,paid_price) VALUES(?,?,?)",(m.from_user.id,name,price))
    db.commit()

    if photo:
        await m.bot.send_photo(m.chat.id, photo, caption=f"🎉 خرید موفق!\n\n👑 {name}")
    else:
        await m.reply(f"🎉 خرید موفق!\n\n👑 {name}")

@dp.message(Command("spin"))
async def spin(m:Message):
    try:
        tier=m.text.split()[1].upper()
    except:
        return await m.reply("استفاده: /spin s | a | b")

    prices={"S":150,"A":100,"B":50}

    if tier not in prices:
        return await m.reply("Tier باید s یا a یا b باشد.")

    cost=prices[tier]

    user(m.from_user.id,m.from_user.full_name)

    size=c.execute("SELECT size FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()[0]

    if size<cost:
        return await m.reply("💸 سانت کافی نداری!")

    pool=[n for n,v in CELEBS.items() if v[0]==tier]
    celeb=random.choice(pool)

    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(cost,m.from_user.id))

    owned=c.execute(
        "SELECT 1 FROM collections WHERE user_id=? AND celeb=?",
        (m.from_user.id,celeb)
    ).fetchone()

    if owned:
        c.execute("UPDATE users SET size=size+? WHERE user_id=?",(cost,m.from_user.id))
        db.commit()
        return await m.reply(
            f"🔄 تکراری بود!\n\n👑 {celeb}\n💰 کل {cost} سانت برگشت داده شد."
        )

    c.execute(
        "INSERT INTO collections(user_id,celeb,paid_price) VALUES(?,?,?)",
        (m.from_user.id,celeb,cost)
    )
    db.commit()

    photo=CELEBS[celeb][3]
    if photo:
        await m.bot.send_photo(m.chat.id, photo, caption=f"🎰 اسپین موفق!\n\n👑 {celeb}")
    else:
        await m.reply(f"🎰 اسپین موفق!\n\n👑 {celeb}")

@dp.message(Command("collectors"))
async def collectors(m:Message):
    rows=c.execute("""
        SELECT users.name,COUNT(collections.celeb) AS total
        FROM users
        LEFT JOIN collections
        ON users.user_id=collections.user_id
        GROUP BY users.user_id
        ORDER BY total DESC
        LIMIT 10
    """).fetchall()

    txt="🏆 بهترین کلکسیونرها\n\n"

    for i,(name,total) in enumerate(rows,1):
        txt+=f"{i}. {name} — {total} سلبریتی\n"

    await m.reply(txt)


@dp.message(Command("list"))
async def list_celeb(m:Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        return await m.reply("Usage: /list [نام] [قیمت]\nمثال: /list Kylie Jenner 500")
    try:
        rest = parts[1].rsplit(None, 1)
        name = rest[0].strip()
        price = int(rest[1])
    except:
        return await m.reply("Usage: /list [نام] [قیمت]\nمثال: /list Kylie Jenner 500")
    if name not in CELEBS:
        return await m.reply("❌ سلبریتی پیدا نشد.")
    user(m.from_user.id, m.from_user.full_name)
    owned = c.execute("SELECT 1 FROM collections WHERE user_id=? AND celeb=?", (m.from_user.id, name)).fetchone()
    if not owned:
        return await m.reply("❌ این سلبریتی رو نداری!")
    # cancel any previous listing for this celeb
    c.execute("UPDATE listings SET active=0 WHERE seller_id=? AND celeb=?", (m.from_user.id, name))
    cur = c.execute("INSERT INTO listings(seller_id, celeb, price) VALUES(?,?,?)", (m.from_user.id, name, price))
    db.commit()
    lid = cur.lastrowid
    tier, orig_price, spin, photo = CELEBS[name]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"🛒 خرید به قیمت {price} سانت", callback_data=f"buyoff:{lid}")
    ]])
    caption = (
        f"🏪 فروش سلبریتی!\n\n"
        f"👑 {name}\n"
        f"💰 قیمت: {price} سانت\n"
        f"👤 فروشنده: {m.from_user.full_name}"
    )
    if photo:
        try:
            await m.bot.send_photo(m.chat.id, photo, caption=caption, reply_markup=kb)
            return
        except:
            pass
    await m.reply(caption, reply_markup=kb)

@dp.callback_query(F.data.startswith("buyoff:"))
async def buyoff(q: CallbackQuery):
    lid = int(q.data.split(":")[1])
    row = c.execute("SELECT seller_id, celeb, price, active FROM listings WHERE id=?", (lid,)).fetchone()
    if not row or row[3] == 0:
        return await q.answer("❌ این آگهی دیگه فعال نیست!", show_alert=True)
    seller_id, name, price, _ = row
    buyer_id = q.from_user.id
    if buyer_id == seller_id:
        return await q.answer("❌ نمیتونی از خودت بخری!", show_alert=True)
    user(buyer_id, q.from_user.full_name)
    buyer_size = c.execute("SELECT size FROM users WHERE user_id=?", (buyer_id,)).fetchone()[0]
    if buyer_size < price:
        return await q.answer("❌ سانت کافی نداری!", show_alert=True)
    # transfer
    c.execute("UPDATE users SET size=size-? WHERE user_id=?", (price, buyer_id))
    c.execute("UPDATE users SET size=size+? WHERE user_id=?", (price, seller_id))
    c.execute("DELETE FROM collections WHERE user_id=? AND celeb=?", (seller_id, name))
    c.execute("INSERT INTO collections(user_id, celeb) VALUES(?,?)", (buyer_id, name))
    c.execute("UPDATE listings SET active=0 WHERE id=?", (lid,))
    db.commit()
    seller_name = c.execute("SELECT name FROM users WHERE user_id=?", (seller_id,)).fetchone()[0]
    await q.message.edit_caption(
        caption=(
            f"✅ معامله انجام شد!\n\n"
            f"👑 {name}\n"
            f"💰 قیمت: {price} سانت\n"
            f"🛒 خریدار: {q.from_user.full_name}\n"
            f"💸 فروشنده: {seller_name}"
        )
    )
    await q.answer("✅ خرید موفق!")

@dp.message(Command("sell"))
async def sell(m:Message):
    name=m.text.replace("/sell","",1).strip()
    if name not in CELEBS:
        return await m.reply("❌ سلبریتی پیدا نشد.")
    user(m.from_user.id,m.from_user.full_name)
    owned=c.execute(
        "SELECT paid_price FROM collections WHERE user_id=? AND celeb=?",
        (m.from_user.id,name)
    ).fetchone()
    if not owned:
        return await m.reply("❌ این سلبریتی رو نداری!")
    paid=owned[0]
    c.execute("DELETE FROM collections WHERE user_id=? AND celeb=?",(m.from_user.id,name))
    c.execute("UPDATE users SET size=size+? WHERE user_id=?",(paid,m.from_user.id))
    db.commit()
    await m.reply(f"💸 فروش موفق!\n\n👑 {name}\n💰 {paid} سانت به حسابت اضافه شد!")

@dp.message(Command("addcm"))
async def addcm(m:Message):
    if m.from_user.id != ADMIN_ID:
        return await m.reply("❌ دسترسی ندارید!")
    try:
        parts = m.text.split()
        amount = int(parts[1])
    except:
        return await m.reply("Usage: /addcm [amount] (reply to a user)")
    if not m.reply_to_message:
        return await m.reply("Reply to a user to add cm.")
    target = m.reply_to_message.from_user.id
    user(target, m.reply_to_message.from_user.full_name)
    c.execute("UPDATE users SET size=size+? WHERE user_id=?", (amount, target))
    db.commit()
    new_size = c.execute("SELECT size FROM users WHERE user_id=?", (target,)).fetchone()[0]
    await m.reply(f"✅ {amount} سانت به {m.reply_to_message.from_user.full_name} اضافه شد!\n📏 اندازه جدید: {new_size} سانت")

async def main():
    bot=Bot(TOKEN)
    from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeDefault
    commands = [
        BotCommand(command="grow", description="🌱 رشد کن"),
        BotCommand(command="size", description="📊 اندازه و پروفایل"),
        BotCommand(command="top", description="🏆 جدول بزرگان"),
        BotCommand(command="market", description="🛒 بازار سلبریتی"),
        BotCommand(command="collection", description="📚 کالکشن من"),
        BotCommand(command="spin", description="🎰 اسپین سلبریتی"),
        BotCommand(command="buy", description="🛍 خرید سلبریتی"),
        BotCommand(command="sell", description="💸 فروش سلبریتی"),
        BotCommand(command="list", description="🏪 فروش به دیگران"),
        BotCommand(command="pvp", description="⚔️ دوئل"),
        BotCommand(command="loan", description="💰 وام دادن"),
        BotCommand(command="repay", description="✅ پرداخت بدهی"),
        BotCommand(command="collectors", description="🏆 بهترین کلکسیونرها"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
    await dp.start_polling(bot)

if __name__=="__main__":
    import asyncio
    asyncio.run(main())
