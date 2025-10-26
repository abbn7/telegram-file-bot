import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# تحميل متغيرات البيئة من ملف bot_config.env
load_dotenv("bot_config.env")

# إعداد التسجيل (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# الحصول على التوكن ومعرف المستخدم المسموح به
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

# "قاعدة بيانات" بسيطة لتخزين معلومات الملفات
# في بيئة إنتاج حقيقية، يجب استخدام قاعدة بيانات مثل PostgreSQL أو MongoDB
# الهيكل: {file_name: {file_id: "...", file_type: "...", uploader_id: "..."}}
files_db = {}

# ----------------------------------------------------------------------
# الدوال المساعدة
# ----------------------------------------------------------------------

def is_allowed_user(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم مسموحًا له بالتفاعل مع البوت."""
    # في هذا المثال، نسمح فقط للمستخدم الذي قدم التوكن بالتحكم في البوت
    return user_id == ALLOWED_USER_ID

async def send_unauthorized_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة عدم تصريح للمستخدم غير المسموح به."""
    await update.message.reply_text(
        "عذرًا، لست مصرحًا لك باستخدام هذا البوت. يرجى التواصل مع المسؤول."
    )

# ----------------------------------------------------------------------
# معالجات الأوامر
# ----------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على الأمر /start."""
    if not is_allowed_user(update.effective_user.id):
        return await send_unauthorized_message(update, context)

    await update.message.reply_text(
        f"أهلاً بك يا {update.effective_user.first_name} في بوت تخزين الملخصات والملفات! 👋\n\n"
        "يمكنك الآن رفع أي ملف (ملخص، كتاب، صورة، فيديو) مباشرة إلى الدردشة.\n"
        "سيتم حفظ الملف باستخدام اسمه الأصلي.\n\n"
        "الأوامر المتاحة:\n"
        "/list - لعرض قائمة بجميع الملفات المخزنة.\n"
        "/delete <اسم_الملف> - لحذف ملف معين (ميزة غير مفعلة في هذا الإصدار المبسط).\n"
        "معرفك الخاص (للتأكد): `{update.effective_user.id}`"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على الأمر /help."""
    if not is_allowed_user(update.effective_user.id):
        return await send_unauthorized_message(update, context)

    await update.message.reply_text(
        "هذا البوت مخصص لتخزين ومشاركة الملفات الدراسية.\n"
        "فقط قم برفع الملف، وسيقوم البوت بحفظه.\n"
        "استخدم /list لعرض الملفات المحفوظة."
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على الأمر /list وعرض الملفات المخزنة."""
    if not is_allowed_user(update.effective_user.id):
        return await send_unauthorized_message(update, context)

    if not files_db:
        await update.message.reply_text("لا توجد ملفات مخزنة حاليًا.")
        return

    message_text = "قائمة الملفات المخزنة:\n\n"
    for i, (file_name, data) in enumerate(files_db.items(), 1):
        file_type = data.get("file_type", "ملف")
        message_text += f"{i}. *{file_name}* (النوع: {file_type})\n"

    await update.message.reply_text(message_text, parse_mode="Markdown")

# ----------------------------------------------------------------------
# معالج الملفات
# ----------------------------------------------------------------------

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة المستندات المرفوعة."""
    if not is_allowed_user(update.effective_user.id):
        return await send_unauthorized_message(update, context)

    # التحقق من وجود مستند
    if update.message.document:
        doc = update.message.document
        file_id = doc.file_id
        file_name = doc.file_name or f"ملف_بدون_اسم_{file_id}"
        file_type = "مستند"

        # حفظ معلومات الملف
        files_db[file_name] = {
            "file_id": file_id,
            "file_type": file_type,
            "uploader_id": update.effective_user.id,
        }

        logger.info(f"تم حفظ المستند: {file_name} بمعرف: {file_id}")
        await update.message.reply_text(
            f"✅ تم حفظ المستند بنجاح!\n"
            f"الاسم: *{file_name}*\n"
            f"المعرف (File ID): `{file_id}`\n"
            "يمكنك استعراضه باستخدام الأمر /list.",
            parse_mode="Markdown"
        )
    else:
        # إذا لم يكن مستندًا، نتحقق من أنواع الملفات الأخرى (صور، فيديوهات، إلخ)
        await handle_other_files(update, context)

async def handle_other_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة أنواع الملفات الأخرى (صور، فيديوهات، إلخ)."""
    if not is_allowed_user(update.effective_user.id):
        # المستخدم غير مصرح له، تم التعامل معه في الدالة السابقة، لكن للتأكد
        return

    # معالجة الصور
    if update.message.photo:
        # نأخذ أكبر صورة (آخر عنصر في القائمة)
        photo = update.message.photo[-1]
        file_id = photo.file_id
        file_type = "صورة"
        file_name = f"صورة_{file_id}"
        
        files_db[file_name] = {
            "file_id": file_id,
            "file_type": file_type,
            "uploader_id": update.effective_user.id,
        }
        logger.info(f"تم حفظ الصورة: {file_name} بمعرف: {file_id}")
        await update.message.reply_text(
            f"✅ تم حفظ الصورة بنجاح!\n"
            f"الاسم: *{file_name}*\n"
            f"المعرف (File ID): `{file_id}`\n"
            "يمكنك استعراضها باستخدام الأمر /list.",
            parse_mode="Markdown"
        )
        return

    # معالجة الفيديوهات
    if update.message.video:
        video = update.message.video
        file_id = video.file_id
        file_type = "فيديو"
        file_name = video.file_name or f"فيديو_{file_id}"

        files_db[file_name] = {
            "file_id": file_id,
            "file_type": file_type,
            "uploader_id": update.effective_user.id,
        }
        logger.info(f"تم حفظ الفيديو: {file_name} بمعرف: {file_id}")
        await update.message.reply_text(
            f"✅ تم حفظ الفيديو بنجاح!\n"
            f"الاسم: *{file_name}*\n"
            f"المعرف (File ID): `{file_id}`\n"
            "يمكنك استعراضه باستخدام الأمر /list.",
            parse_mode="Markdown"
        )
        return

    # معالجة الرسائل النصية التي ليست أوامر
    if update.message.text:
        # تجاهل الرسائل النصية التي ليست أوامر
        return

    # الرد على أنواع الرسائل الأخرى غير المدعومة
    await update.message.reply_text(
        "نوع الملف غير مدعوم حاليًا أو لم يتم التعرف على الرسالة. يرجى رفع مستند أو صورة أو فيديو."
    )

# ----------------------------------------------------------------------
# معالج استرجاع الملفات
# ----------------------------------------------------------------------

async def retrieve_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """استرجاع الملف عن طريق اسمه."""
    if not is_allowed_user(update.effective_user.id):
        return await send_unauthorized_message(update, context)

    # نتوقع أن يكون اسم الملف هو الوسيط الأول بعد الأمر /get
    if not context.args:
        await update.message.reply_text(
            "يرجى تحديد اسم الملف الذي تريد استرجاعه. مثال: `/get اسم_الملف`",
            parse_mode="Markdown"
        )
        return

    file_name = " ".join(context.args)

    if file_name in files_db:
        file_data = files_db[file_name]
        file_id = file_data["file_id"]
        file_type = file_data["file_type"]

        await update.message.reply_text(
            f"جاري إرسال الملف: *{file_name}* (النوع: {file_type})...",
            parse_mode="Markdown"
        )
        
        try:
            # إرسال الملف باستخدام file_id
            if file_type == "مستند":
                await context.bot.send_document(chat_id=update.effective_chat.id, document=file_id)
            elif file_type == "صورة":
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)
            elif file_type == "فيديو":
                await context.bot.send_video(chat_id=update.effective_chat.id, video=file_id)
            else:
                # كحل أخير، نحاول إرساله كمستند
                await context.bot.send_document(chat_id=update.effective_chat.id, document=file_id)

        except Exception as e:
            logger.error(f"فشل في إرسال الملف {file_name}: {e}")
            await update.message.reply_text(
                f"عذرًا، حدث خطأ أثناء محاولة إرسال الملف *{file_name}*.\n"
                "قد يكون الملف غير صالح أو تم حذفه من سيرفرات تلجرام.",
                parse_mode="Markdown"
            )

    else:
        await update.message.reply_text(
            f"عذرًا، لم يتم العثور على ملف بالاسم: *{file_name}*.\n"
            "استخدم /list لعرض جميع الملفات.",
            parse_mode="Markdown"
        )

# ----------------------------------------------------------------------
# الدالة الرئيسية
# ----------------------------------------------------------------------

def main() -> None:
    """تشغيل البوت."""
    if not BOT_TOKEN:
        logger.error("لم يتم العثور على BOT_TOKEN في ملف bot_config.env. يرجى التأكد من صحة التوكن.")
        return
    
    if not ALLOWED_USER_ID:
        logger.error("لم يتم العثور على ALLOWED_USER_ID في ملف bot_config.env. يرجى التأكد من صحة معرف المستخدم.")
        return

    # إنشاء التطبيق وتمرير التوكن
    application = Application.builder().token(BOT_TOKEN).build()

    # معالجات الأوامر
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("get", retrieve_file))

    # معالج الملفات (المستندات، الصور، الفيديوهات)
    # نستخدم filters.ALL لضمان معالجة جميع أنواع الرسائل
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_document))

    # تشغيل البوت
    logger.info("بدء تشغيل البوت...")
    # استخدام run_polling لبيئة التطوير والاختبار
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

