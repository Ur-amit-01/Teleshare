import asyncio
from pyrogram import Client, filters
from pyrogram.errors import UsernameNotOccupied
from pyrogram.types import Message

ERROR_MESSAGE = False 

class batch_temp(object):
    IS_BATCH = {}

@Client.on_message(filters.command(["cancel"]))
async def send_cancel(client: Client, message: Message):
    batch_temp.IS_BATCH[message.from_user.id] = True
    await message.reply("**Batch Successfully Cancelled.**")

@Client.on_message(filters.text & filters.private & filters.regex("https://t.me/"))
async def save(client: Client, message: Message):
    if "https://t.me/" in message.text:
        if "?start=" in message.text:
            return
        
        if batch_temp.IS_BATCH.get(message.from_user.id) == False:
            return await message.reply("**One Task Is Already Processing. Wait For It To Complete. If You Want To Cancel This Task Then Use - /cancel**")

        datas = message.text.split("/")
        
        if len(datas) < 5:
            return
        
        if "?" in datas[3]:
            return
        
        try:
            msg_part = datas[-1].split("?")[0]
            temp = msg_part.split("-")
            fromID = int(temp[0].strip())
            toID = int(temp[1].strip()) if len(temp) > 1 else fromID
        except (ValueError, IndexError):
            return

        batch_temp.IS_BATCH[message.from_user.id] = False

        try:
            for msgid in range(fromID, toID + 1):
                if batch_temp.IS_BATCH.get(message.from_user.id):
                    break

                username = datas[3]
                
                try:
                    msg = await client.get_messages(username, msgid)
                except:
                    continue
                    
                try:
                    await client.copy_message(message.chat.id, msg.chat.id, msg.id)
                except:
                    pass

                await asyncio.sleep(0.3)

        finally:
            batch_temp.IS_BATCH[message.from_user.id] = True
