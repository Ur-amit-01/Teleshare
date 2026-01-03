import datetime
from typing import ClassVar

import tzlocal
from lru import LRU
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.types import Message

from bot.config import config
from bot.database import MongoDB

database = MongoDB()


class SubscriptionMessage(Message):
    def __init__(self) -> None:
        self.user_is_banned = False


class SubscriptionFilter:
    """
    A filter to check if a user is subscribed to the required channels.

    Attributes:
        CACHE_USER_SECONDS (int): Amount of seconds before checking the user again to avoid spams.
        _subs_cache (ClassVar[LRU[int, datetime.datetime]]): A lru dict to store user IDs and their last check time.
    """

    CACHE_USER_SECONDS: int = 15
    _subs_cache: ClassVar[LRU] = LRU(10)

    @classmethod
    def subscription(cls) -> filters.Filter:
        """
        Creates a filter to check if a user is subscribed to the required channels.

        Returns:
            filters.Filter: A filter to check if a user is subscribed to the required channels.
        """

        async def func(flt: None, client: Client, message: SubscriptionMessage) -> bool:  # noqa: ARG001
            """
            Checks if a user is subscribed to the required channels.

            Parameters:
                client (Client): The Pyrogram client.
                message (Message): The message to check.

            Returns:
                bool: True if the user is subscribed, False otherwise.
            """

            user_id = message.from_user.id
            status = [
                ChatMemberStatus.OWNER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.MEMBER,
            ]

            if await database.is_user_banned(user_id):
                message.user_is_banned = True
                return False

            if user_id in config.ROOT_ADMINS_ID or not config.FORCE_SUB_CHANNELS:
                return True

            if user_id in cls._subs_cache:
                user_cache_time = cls._subs_cache.get(user_id)
                current_time = datetime.datetime.now(tz=tzlocal.get_localzone())

                if user_cache_time and (current_time - user_cache_time) <= datetime.timedelta(
                    seconds=cls.CACHE_USER_SECONDS,
                ):
                    return True

                cls._subs_cache.pop(user_id)

            # Track if user has joined all channels
            all_channels_joined = True
            joined_request_channel = await database.user_requested_channels(user_id) if config.PRIVATE_REQUEST else []

            for channel_info in config.channels_n_invite.values():
                channel_id = channel_info["channel_id"]

                try:
                    member = await client.get_chat_member(chat_id=channel_id, user_id=user_id)

                    if member.status not in status:
                        all_channels_joined = False

                except UserNotParticipant:
                    if (not config.PRIVATE_REQUEST) or (channel_id not in joined_request_channel):
                        all_channels_joined = False

            # Only cache and return True if user has joined ALL channels
            if all_channels_joined:
                cls._subs_cache[user_id] = datetime.datetime.now(tz=tzlocal.get_localzone())
                return True
            else:
                return False

        return filters.create(func, "SubscriptionFilter")
