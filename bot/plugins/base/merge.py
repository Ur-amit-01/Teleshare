import os
import time
import tempfile
import asyncio
import humanize
from PIL import Image
from pyrogram import Client, filters
from PyPDF2 import PdfMerger
from pyrogram.types import Message, ForceReply

MAX_FILE_SIZE = 350 * 1024 * 1024  # 350MB

user_file_metadata = {}
user_states = {}
pending_filename_requests = {}

async def reset_user_state(user_id: int):
    await asyncio.sleep(300)
    user_file_metadata.pop(user_id, None)
    pending_filename_requests.pop(user_id, None)
    user_states.pop(user_id, None)

async def show_progress_bar(progress_message, current, total, bar_length=10):
    progress = min(current / total, 1.0)
    filled_length = int(bar_length * progress)
    bar = "●" * filled_length + "○" * (bar_length - filled_length)
    percentage = int(progress * 100)
    text = f"**Merging... 📃 + 📃**\n`[{bar}]` {percentage}%"
    await progress_message.edit_text(text)

async def show_upload_progress_bar(current, total, start_time):
    elapsed_time = time.time() - start_time
    upload_speed = current / elapsed_time if elapsed_time > 0 else 0
    progress = min(current / total, 1.0)
    percentage = int(progress * 100)
    remaining_time = (total - current) / upload_speed if upload_speed > 0 else 0

    progress_bar = (
        f"**╭━━━━❰ Uploading... ❱━➣**\n"
        f"**┣⪼ 🗂️ : {humanize.naturalsize(current)} | {humanize.naturalsize(total)}**\n"
        f"**┣⪼ ⏳️ : {percentage}%\n"
        f"**┣⪼ 🚀 : {humanize.naturalsize(upload_speed)}/s**\n"
        f"**┣⪼ ⏱️ : {humanize.precisedelta(remaining_time)}**\n"
        f"**╰━━━━━━━━━━━━━━━➣**"
    )
    return progress_bar

async def start_file_collection(client: Client, message: Message):
    user_id = message.from_user.id
    user_file_metadata[user_id] = []
    user_states[user_id] = "collecting_files"
    await message.reply_text("**📤 ɴᴏᴡ ꜱᴇɴᴅ ʏᴏᴜʀ ғɪʟᴇs ɪɴ sᴇǫᴜᴇɴᴄᴇ !! 🧾**")
    asyncio.create_task(reset_user_state(user_id))

async def handle_pdf_metadata(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_states or user_states[user_id] != "collecting_files":
        return

    if message.document.mime_type != "application/pdf":
        await message.reply_text("❌ This is not a valid PDF file. Please send a PDF 📑.")
        return

    if len(user_file_metadata[user_id]) >= 20:
        await message.reply_text("⚠️ You can merge only 20 files at once. Type /done ✅ to merge them.")
        return

    if message.document.file_size > MAX_FILE_SIZE:
        await message.reply_text("🚫 File size is too large! Please send a file under 350MB.")
        return

    file_name = message.document.file_name
    if any(file_data["file_name"] == file_name for file_data in user_file_metadata[user_id]):
        timestamp = int(time.time())
        file_name = f"{os.path.splitext(file_name)[0]}_{timestamp}{os.path.splitext(file_name)[1]}"

    user_file_metadata[user_id].append({
        "type": "pdf",
        "file_id": message.document.file_id,
        "file_name": file_name,
    })
    
    await message.reply_text(
        f"•**ᴛᴏᴛᴀʟ ꜰɪʟᴇꜱ: {len(user_file_metadata[user_id])} 📄**\n"
        "•**/done: ᴛᴏ ᴍᴇʀɢᴇ ᴀʟʟ ꜰɪʟᴇꜱ ✅**"
    )

async def handle_image_metadata(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_states or user_states[user_id] != "collecting_files":
        return

    file_name = f"photo_{len(user_file_metadata[user_id]) + 1}.jpg"
    if any(file_data["file_name"] == file_name for file_data in user_file_metadata[user_id]):
        timestamp = int(time.time())
        file_name = f"{os.path.splitext(file_name)[0]}_{timestamp}{os.path.splitext(file_name)[1]}"

    user_file_metadata[user_id].append({
        "type": "image",
        "file_id": message.photo.file_id,
        "file_name": file_name,
    })
    
    await message.reply_text(
        f"•**ᴛᴏᴛᴀʟ ɪᴍᴀɢᴇꜱ: {len(user_file_metadata[user_id])} 🖼️\n"
        "•**/done: ᴛᴏ ᴍᴇʀɢᴇ ᴀʟʟ ɪᴍᴀɢᴇꜱ ✅**"
    )

async def merge_files(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_file_metadata or not user_file_metadata[user_id]:
        await message.reply_text("**⚠️ Yᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴀᴅᴅᴇᴅ ᴀɴʏ ғɪʟᴇs ʏᴇᴛ. Usᴇ /merge ᴛᴏ sᴛᴀʀᴛ.**")
        return

    filename_request_message = await message.reply_text(
        "**✍️ Type a name for your merged PDF 📄.**",
        reply_markup=ForceReply(selective=True)
    )
    user_states[user_id] = "waiting_for_filename"
    pending_filename_requests[user_id] = filename_request_message.id

async def handle_filename(client: Client, message: Message):
    user_id = message.from_user.id

    if not (user_id in user_states and user_states[user_id] == "waiting_for_filename" and 
            message.reply_to_message and message.reply_to_message.from_user.is_self):
        return

    custom_filename = message.text.strip()
    if not custom_filename:
        await message.reply_text("❌ Filename cannot be empty. Please try again.")
        return

    if user_id in pending_filename_requests:
        try:
            await client.delete_messages(message.chat.id, pending_filename_requests[user_id])
        except:
            pass
        pending_filename_requests.pop(user_id, None)

    progress_message = await message.reply_text("**🛠️ Merging files... Please wait... ⏰**")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, f"{custom_filename}.pdf")
            merger = PdfMerger()

            total_files = len(user_file_metadata[user_id])
            for index, file_data in enumerate(user_file_metadata[user_id], start=1):
                if file_data["type"] == "pdf":
                    file_path = await client.download_media(file_data["file_id"], 
                                                           file_name=os.path.join(temp_dir, file_data["file_name"]))
                    merger.append(file_path)
                elif file_data["type"] == "image":
                    img_path = await client.download_media(file_data["file_id"], 
                                                          file_name=os.path.join(temp_dir, file_data["file_name"]))
                    image = Image.open(img_path).convert("RGB")
                    img_pdf_path = os.path.join(temp_dir, f"{os.path.splitext(file_data['file_name'])[0]}.pdf")
                    image.save(img_pdf_path, "PDF")
                    merger.append(img_pdf_path)
                
                await show_progress_bar(progress_message, index, total_files)

            merger.write(output_file)
            merger.close()

            start_time = time.time()
            async def progress_callback(current, total):
                progress_bar = await show_upload_progress_bar(current, total, start_time)
                await progress_message.edit_text(progress_bar)

            await client.send_document(
                chat_id=message.chat.id,
                document=output_file,
                caption="**🎉 Here is your merged PDF 📄.**",
                progress=progress_callback,
            )

            await client.send_sticker(
                chat_id=message.chat.id,
                sticker="CAACAgIAAxkBAAEWFCFnmnr0Tt8-3ImOZIg9T-5TntRQpAAC4gUAAj-VzApzZV-v3phk4DYE"
            )

            await progress_message.delete()

    except Exception as e:
        await progress_message.edit_text(f"❌ Failed to merge files: {e}")

    finally:
        user_file_metadata.pop(user_id, None)
        user_states.pop(user_id, None)
        pending_filename_requests.pop(user_id, None)

# Register handlers
@Client.on_message(filters.command(["merge"]))
async def start_file_collection_handler(client: Client, message: Message):
    await start_file_collection(client, message)

@Client.on_message(filters.document & filters.private)
async def handle_pdf_metadata_handler(client: Client, message: Message):
    await handle_pdf_metadata(client, message)

@Client.on_message(filters.photo & filters.private)
async def handle_image_metadata_handler(client: Client, message: Message):
    await handle_image_metadata(client, message)

@Client.on_message(filters.command(["done"]))
async def merge_files_handler(client: Client, message: Message):
    await merge_files(client, message)

@Client.on_message(filters.text & filters.private & filters.reply)
async def handle_filename_handler(client: Client, message: Message):
    await handle_filename(client, message)
