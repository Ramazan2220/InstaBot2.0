# Состояния для ConversationHandler
# Используются в handlers.py

# Состояния для добавления аккаунта
WAITING_USERNAME = 1
WAITING_PASSWORD = 2

# Состояния для настройки профиля
WAITING_ACCOUNT_SELECTION = 3
WAITING_BIO_OR_AVATAR = 4

# Состояния для публикации
WAITING_TASK_TYPE = 5
WAITING_MEDIA = 6
WAITING_CAPTION = 7

# Состояния для отложенной публикации
WAITING_SCHEDULE_TIME = 8

# Состояния для добавления прокси
WAITING_PROXY_INFO = 9

# Добавьте новую константу
BULK_ADD_ACCOUNTS = 10

# Состояния для настройки профиля
PROFILE_MENU = 100
EDIT_PROFILE_NAME = 101
EDIT_USERNAME = 102
EDIT_BIO = 103
EDIT_LINKS = 104
UPLOAD_PROFILE_PHOTO = 105
UPLOAD_POST = 106
ENTER_POST_CAPTION = 107
CONFIRM_PIN_POST = 108
CONFIRM_DELETE_PROFILE_PHOTO = 109
CONFIRM_DELETE_POSTS = 110
CONFIRM_DELETE_BIO = 111

# Состояния для управления профилем
class ProfileStates:
    EDIT_NAME = 20
    EDIT_USERNAME = 21
    EDIT_BIO = 22
    EDIT_LINKS = 23
    ADD_PHOTO = 24
    ADD_POST = 25

# Состояния для управления фото профиля
WAITING_PROFILE_PHOTO = 11