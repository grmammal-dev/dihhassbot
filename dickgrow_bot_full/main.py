
import os, sqlite3, random, time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

TOKEN = os.getenv("BOT_TOKEN")
DB="database.db"
COOLDOWN=3*60*60

db=sqlite3.connect(DB)
c=db.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,name TEXT,size INTEGER DEFAULT 0,debt INTEGER DEFAULT 0,last_grow INTEGER DEFAULT 0)")
c.execute("CREATE TABLE IF NOT EXISTS battles(id INTEGER PRIMARY KEY AUTOINCREMENT,creator INTEGER,bet INTEGER,active INTEGER DEFAULT 1)")
c.execute("CREATE TABLE IF NOT EXISTS loans(lender_id INTEGER, borrower_id INTEGER, amount INTEGER)")
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
    delta=random.randint(400,500)
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
c.execute("CREATE TABLE IF NOT EXISTS collections(user_id INTEGER, celeb TEXT)")
db.commit()


CELEBS = {
    "Ana de Armas": ("S",300,150,"AgACAgQAAxkBAAEfCvFqJGF9gHeK-FdL3g8Dci7TQNEoggAC2Q1rG3tMKVFs57x8-y1feQEAAwIAA3gAAzsE"),
    "Madison Beer": ("S",300,150,"AgACAgQAAxkBAAEfCv9qJGKST7WbNyfzkzP1WSoI1Iu2cgAC2w1rG3tMKVHiqz1XQ-d6zAEAAwIAA3gAAzsE"),
    "Georgina Rodriguez": ("S",300,150,"AgACAgQAAxkBAAEfCvlqJGIXIENSIjrMMnLZoHS7AVxU1QAC2g1rG3tMKVFEyBOLad49wgEAAwIAA3gAAzsE"),
    "Kylie Jenner": ("S",300,150,"AgACAgQAAxkBAAEfCslqJF4aGLfY3nWNvS572NxehqwhiAACsBJrGzNwKVFiDAiqRzQvkgEAAwIAA3gAAzsE"),
    "Sydney Sweeney": ("S",300,150,"AgACAgQAAxkBAAEfCtNqJF-RQinO1Aw9eVUcLjW1ChLosQAC1A1rG3tMKVFWcBdZYVaR7wEAAwIAA3kAAzsE"),
    "Olivia Cooke": ("A",200,100,None),
    "Scarlett Johansson": ("A",200,100,"AgACAgQAAxkBAAEfCstqJF7mY7jY4yYqDgFc3uWfgkGEeAAC0Q1rG3tMKVE3ZBCFgWdpKQEAAwIAA3kAAzsE"),
    "Sabrina Carpenter": ("A",200,100,"AgACAgQAAxkBAAEfCuFqJGA8mGq78iqNtgsem5PSDj05LwAC1g1rG3tMKVG7fYDaui3BJAEAAwIAA3gAAzsE"),
    "Olivia Rodrigo": ("A",200,100,"AgACAgQAAxkBAAEfCwFqJGL8g2q8giApiK3Jk-VXJ-lH6gAC3A1rG3tMKVFfIoq12SC3aQEAAwIAA3kAAzsE"),
    "Kendall Jenner": ("A",200,100,"AgACAgQAAxkBAAEfCwNqJGOYTT7JYWQuSqGtj9atlc3T3AAC3Q1rG3tMKVEHQ57PLiwgpgEAAwIAA3kAAzsE"),
    "Kathryn Newton": ("B",100,50,None),
    "Margot Robbie": ("B",100,50,None),
    "Taylor Swift": ("B",100,50,None),
    "Dua Lipa": ("B",100,50,None),
    "Megan Fox": ("B",100,50,None),
}


@dp.message(Command("market"))
async def market(m:Message):
    await m.reply("🛒 بازار سلبریتی\n\n🥇 S (300)\nAna de Armas\nMadison Beer\nGeorgina Rodriguez\nKylie Jenner\nSydney Sweeney\n\n🥈 A (200)\nOlivia Cooke\nScarlett Johansson\nSabrina Carpenter\nOlivia Rodrigo\nKendall Jenner\n\n🥉 B (100)\nKathryn Newton\nMargot Robbie\nTaylor Swift\nDua Lipa\nMegan Fox\n\n🎰 /spin s | a | b")

@dp.message(Command("collection"))
async def collection(m:Message):
    rows=c.execute("SELECT celeb FROM collections WHERE user_id=?",(m.from_user.id,)).fetchall()
    if not rows:
        return await m.reply("📚 هنوز چیزی نداری.")
    await m.reply("📚 کالکشن شما\n\n" + "\n".join("👑 "+r[0] for r in rows))


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
        "SELECT 1 FROM collections WHERE user_id=? AND celeb=?",
        (m.from_user.id,name)
    ).fetchone()

    if owned:
        return await m.reply("📚 این سلبریتی رو داری!")

    c.execute("UPDATE users SET size=size-? WHERE user_id=?",(price,m.from_user.id))
    c.execute("INSERT INTO collections(user_id,celeb) VALUES(?,?)",(m.from_user.id,name))
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
        "INSERT INTO collections(user_id,celeb) VALUES(?,?)",
        (m.from_user.id,celeb)
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


async def main():
    bot=Bot(TOKEN)
    await dp.start_polling(bot)

if __name__=="__main__":
    import asyncio
    asyncio.run(main())

@dp.message(Command("testphoto"))
async def testphoto(m: Message):
    await m.bot.send_photo(
        chat_id=m.chat.id,
        photo="AgACAgQAAxkBAAEfCslqJF4aGLfY3nWNvS572NxehqwhiAACsBJrGzNwKVFiDAiqRzQvkgEAAwIAA3gAAzsE",
        caption="Kylie Test"
    )
