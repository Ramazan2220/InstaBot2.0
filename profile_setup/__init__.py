import logging
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# Состояния для ConversationHandler
EDIT_NAME, EDIT_USERNAME, EDIT_BIO, EDIT_LINKS, ADD_PHOTO, ADD_POST = range(6)

# Импортируем функции из модулей
from .name_manager import edit_profile_name, save_profile_name
from .username_manager import edit_profile_username, save_profile_username
from .bio_manager import edit_profile_bio, save_profile_bio, delete_bio
from .links_manager import edit_profile_links, save_profile_links
from .avatar_manager import add_profile_photo, save_profile_photo, delete_profile_photo
from .post_manager import add_post, save_post
from .cleanup_manager import delete_all_posts
from .common import profile_setup_menu, profile_account_menu, cancel

logger = logging.getLogger(__name__)

def get_profile_handlers():
    """Возвращает обработчики для управления профилем"""
    profile_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_profile_name, pattern='^profile_edit_name$'),
            CallbackQueryHandler(edit_profile_username, pattern='^profile_edit_username$'),
            CallbackQueryHandler(edit_profile_bio, pattern='^profile_edit_bio$'),
            CallbackQueryHandler(edit_profile_links, pattern='^profile_edit_links$'),
            CallbackQueryHandler(add_profile_photo, pattern='^profile_add_photo$'),
            CallbackQueryHandler(add_post, pattern='^profile_add_post$'),
        ],
        states={
            EDIT_NAME: [MessageHandler(Filters.text & ~Filters.command, save_profile_name)],
            EDIT_USERNAME: [MessageHandler(Filters.text & ~Filters.command, save_profile_username)],
            EDIT_BIO: [MessageHandler(Filters.text & ~Filters.command, save_profile_bio)],
            EDIT_LINKS: [MessageHandler(Filters.text & ~Filters.command, save_profile_links)],
            ADD_PHOTO: [MessageHandler(Filters.photo, save_profile_photo)],
            ADD_POST: [
                MessageHandler(Filters.photo | Filters.video, save_post),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern='^profile_account_'),
            CallbackQueryHandler(cancel, pattern='^profile_setup$'),
        ],
        name="profile_conversation",
        persistent=False,
    )

    handlers = [
        CommandHandler('profile', profile_setup_menu),
        CallbackQueryHandler(profile_setup_menu, pattern='^profile_setup$'),
        CallbackQueryHandler(profile_account_menu, pattern='^profile_account_'),
        CallbackQueryHandler(delete_profile_photo, pattern='^profile_delete_photo$'),
        CallbackQueryHandler(add_profile_photo, pattern='^add_profile_photo_\d+$'),  
        CallbackQueryHandler(delete_all_posts, pattern='^profile_delete_posts$'),
        CallbackQueryHandler(delete_bio, pattern='^profile_delete_bio$'),
        profile_conv_handler,
    ]

    return handlers