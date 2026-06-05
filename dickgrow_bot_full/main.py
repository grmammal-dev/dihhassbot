
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
        return await m.reply(f"⏳ Wait {rem} minutes.")
    delta=random.randint(1,10) if random.random()<0.8 else -random.randint(1,5)
    size=max(0,size+delta)
    c.execute("UPDATE users SET size=?,last_grow=? WHERE user_id=?",(size,now,m.from_user.id)); db.commit()
    await m.reply(f"🍆 {delta:+} cm\nSize: {size} cm")

@dp.message(Command("size"))
async def size(m:Message):
    user(m.from_user.id,m.from_user.full_name)
    s,d=c.execute("SELECT size,debt FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()
    await m.reply(f"🍆 Size: {s} cm\n💸 Debt: {d} cm")

@dp.message(Command("borrow"))
async def borrow(m:Message):
    try: amt=int(m.text.split()[1])
    except: return await m.reply("Usage: /borrow 5")
    user(m.from_user.id,m.from_user.full_name)
    s,d=c.execute("SELECT size,debt FROM users WHERE user_id=?",(m.from_user.id,)).fetchone()
    c.execute("UPDATE users SET size=?,debt=? WHERE user_id=?",(s+amt,d+amt,m.from_user.id)); db.commit()
    await m.reply(f"🏦 Borrowed {amt} cm")

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
    txt="🏆 Leaderboard\n\n"
    for i,(n,s) in enumerate(rows,1): txt+=f"{i}. {n} — {s} cm\n"
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
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Accept PvP",callback_data=f"pvp:{bid}")]])
winner_name = c.execute(
    "SELECT name FROM users WHERE user_id=?",
    (winner,)
).fetchone()[0]

await q.message.edit_text(
    f"⚔️ Battle finished!\n🏆 Winner: {winner_name}\n💰 Prize: {bet} cm"
)
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
    await q.message.edit_text(f"⚔️ Battle finished!\nWinner ID: {winner}\nPrize: {bet} cm")

async def main():
    bot=Bot(TOKEN)
    await dp.start_polling(bot)

if __name__=="__main__":
    import asyncio
    asyncio.run(main())
