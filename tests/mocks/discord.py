import json
from contextlib import asynccontextmanager

from . import AsyncMock


class MockFile:
    def __init__(self, fp):
        self.fp = fp


class MockAttachment:
    def __init__(self, filename, data):
        self.filename = filename
        self.data = data

    async def read(self, *, use_cached=False):
        return self.data


class MockDiscordMessage:
    MOCK_DISCORD_MESSAGE_ID_START = 5000

    def __init__(self):
        self.id = MockDiscordMessage.MOCK_DISCORD_MESSAGE_ID_START
        self.channel = MockChannel("id", "text")
        MockDiscordMessage.MOCK_DISCORD_MESSAGE_ID_START += 1
        self.reactions = []
        self.delete = AsyncMock()

        # edited is a spy for tracking calls to edit(), it doesn't exist on the real obj.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_edited_XXX` and `all_edited_XXX` to make our lives easier.
        self.edited = AsyncMock()

    async def add_reaction(self, emoji):
        self.reactions.append(emoji)

    async def clear_reactions(self):
        self.reactions = []

    async def remove_reaction(self, emoji, user):
        done = False
        update = []
        for reaction in self.reactions:
            if not done and reaction == emoji:
                done = True
                continue
            update.append(reaction)
        self.reactions = update

    async def edit(self, content=None, *args, **kwargs):
        await self.edited(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )

    @property
    def last_edited_call(self):
        args, kwargs = self.edited.call_args
        return {"args": args, "kwargs": kwargs}

    @property
    def last_edited_response(self):
        return self.all_edited_responses[-1]

    @property
    def last_edited_embed(self):
        return self.last_edited_call["kwargs"]["embed"].to_dict()

    @property
    def all_edited_calls(self):
        edited_calls = []
        for edited_call in self.edited.call_args_list:
            args, kwargs = edited_call
            edited_calls.append({"args": args, "kwargs": kwargs})
        return edited_calls

    @property
    def all_edited_responses(self):
        return [edited_call["args"][0] for edited_call in self.all_edited_calls]

    @property
    def all_edited_embeds(self):
        return [
            edited_call["kwargs"]["embed"].to_dict()
            for edited_call in self.all_edited_calls
            if "embed" in edited_call["kwargs"]
        ]


class MockPayload:
    def __init__(self, user_id, emoji, channel_id, message_id, guild_id, member=None):
        self.member = member
        self.user_id = user_id
        self.emoji = emoji
        self.channel_id = channel_id
        self.message_id = message_id
        self.guild_id = guild_id


def send_side_effect(*args, **kwargs):
    return MockDiscordMessage()


class MockMember:
    def __init__(self, member_name, member_id, roles=[], admin=False, owner=False):
        self.name = member_name
        self.nick = None
        self.id = member_id
        self.roles = roles
        self.avatar_url = "http://example.com/avatar.png"
        self.bot = False
        self.admin = admin
        self.owner = owner
        self.avatar = None

        for role in roles:
            role.members.add(self)

        # sent is a spy for tracking calls to send(), it doesn't exist on the real object.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_sent_XXX` and `all_sent_XXX` to make our lives easier.
        self.sent = AsyncMock(side_effect=send_side_effect)
        self.last_sent_message = None

    async def send(self, content=None, *args, **kwargs):
        self.last_sent_message = await self.sent(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )
        return self.last_sent_message

    def permissions_in(self, channel):
        class MockPermissions:
            def __init__(self, administrator):
                self.administrator = administrator
                self.value = 268528731
                self.read_messages = True
                self.add_reactions = True
                self.manage_messages = True

        return MockPermissions(self.admin)

    @property
    def mention(self):
        return f"<@{self.id}>"

    @property
    def last_sent_call(self):
        args, kwargs = self.sent.call_args
        return {"args": args, "kwargs": kwargs}

    @property
    def last_sent_response(self):
        return self.all_sent_responses[-1]

    @property
    def last_sent_embed(self):
        return self.last_sent_call["kwargs"]["embed"].to_dict()

    @property
    def all_sent_calls(self):
        sent_calls = []
        for sent_call in self.sent.call_args_list:
            args, kwargs = sent_call
            sent_calls.append({"args": args, "kwargs": kwargs})
        return sent_calls

    @property
    def all_sent_responses(self):
        return [sent_call["args"][0] for sent_call in self.all_sent_calls]

    @property
    def all_sent_embeds(self):
        return [
            sent_call["kwargs"]["embed"].to_dict()
            for sent_call in self.all_sent_calls
            if "embed" in sent_call["kwargs"]
        ]

    @property
    def all_sent_files(self):
        return [
            sent_call["kwargs"]["file"]
            for sent_call in self.all_sent_calls
            if "file" in sent_call["kwargs"]
        ]

    @property
    def all_sent_embeds_json(self):
        return json.dumps(self.all_sent_embeds, indent=4, sort_keys=True)

    def __repr__(self):
        return f"{self.name}#{self.id}"


class MockRole:
    def __init__(self, name, members=None):
        self.name = name
        self.members = set(members or [])


def create_voice_channel_side_effect(*args, **kwargs):
    class MockInvite:
        def __init__(self):
            self.url = "http://fake-invite-url"

    class MockVoiceChannel:
        def __init__(self):
            self.id = 1
            self.create_invite = AsyncMock(return_value=MockInvite())

    return MockVoiceChannel()


def create_category_channel_side_effect(*args, **kwargs):
    class MockCategoryChannel:
        def __init__(self):
            self.id = 2

    return MockCategoryChannel()


class MockGuild:
    def __init__(self, guild_id, name, members):
        self.id = guild_id
        self.name = name
        self.members = members
        self.categories = []
        self.owner_id = 0
        self.me = MockMember("bot", 0, [], True, True)
        self.roles = []

        self.create_voice_channel = AsyncMock(
            side_effect=create_voice_channel_side_effect
        )

        self.create_category_channel = AsyncMock(
            side_effect=create_category_channel_side_effect
        )

    def get_member(self, member_id):
        return next((member for member in self.members if member.id == member_id), None)


class MockChannel:
    """Don't create this directly, use the channel_maker fixture instead."""

    def __init__(self, channel_id, channel_type):
        self.id = channel_id
        self.type = channel_type
        self.guild = MockGuild(1, "guild", [])
        self.delete = AsyncMock()

        # sent is a spy for tracking calls to send(), it doesn't exist on the real object.
        # There are also helpers for inspecting calls to sent defined on this class of
        # the form `last_sent_XXX` and `all_sent_XXX` to make our lives easier.
        self.sent = AsyncMock(side_effect=send_side_effect)
        self.last_sent_message = None
        self.messages = []

    async def send(self, content=None, *args, **kwargs):
        self.last_sent_message = await self.sent(
            content,
            **{param: value for param, value in kwargs.items() if value is not None},
        )
        self.last_sent_message.channel = self
        self.messages.append(self.last_sent_message)
        return self.last_sent_message

    async def fetch_message(self, message_id):
        for message in self.messages:
            if message.id == message_id:
                return message
        return None

    @property
    def last_sent_call(self):
        args, kwargs = self.sent.call_args
        return {"args": args, "kwargs": kwargs}

    @property
    def last_sent_response(self):
        return self.all_sent_responses[-1]

    @property
    def last_sent_embed(self):
        return self.last_sent_call["kwargs"]["embed"].to_dict()

    @property
    def all_sent_calls(self):
        sent_calls = []
        for sent_call in self.sent.call_args_list:
            args, kwargs = sent_call
            sent_calls.append({"args": args, "kwargs": kwargs})
        return sent_calls

    @property
    def all_sent_responses(self):
        return [sent_call["args"][0] for sent_call in self.all_sent_calls]

    @property
    def all_sent_embeds(self):
        return [
            sent_call["kwargs"]["embed"].to_dict()
            for sent_call in self.all_sent_calls
            if "embed" in sent_call["kwargs"]
        ]

    @property
    def all_sent_files(self):
        return [
            sent_call["kwargs"]["file"]
            for sent_call in self.all_sent_calls
            if "file" in sent_call["kwargs"]
        ]

    @property
    def all_sent_embeds_json(self):
        return json.dumps(self.all_sent_embeds, indent=4, sort_keys=True)

    @asynccontextmanager
    async def typing(self):
        yield


class MockTextChannel(MockChannel):
    """Don't create this directly, use the channel_maker fixture instead."""

    def __init__(self, channel_id, channel_name, members):
        super().__init__(channel_id, "text")
        self.name = channel_name
        self.members = members
        self.guild = MockGuild(500, "Guild Name", members)

    def permissions_for(self, member):
        class MockPermissions:
            def __init__(self):
                self.read_messages = True

        return MockPermissions()


class MockVoiceChannel(MockChannel):
    """Don't create this directly, use the channel_maker fixture instead."""

    def __init__(self, channel_id, channel_name, members):
        super().__init__(channel_id, "voice")
        self.name = channel_name
        self.members = members
        self.voice_states = {member.id: member.name for member in members}
        self.guild = MockGuild(500, "Guild Name", members)
        self.create_invite = AsyncMock()


class MockDM(MockChannel):
    """Don't create this directly, use the channel_maker fixture instead."""

    def __init__(self, channel_id):
        super().__init__(channel_id, "private")
        self.recipient = None  # can't be set until we know the author of a message


class MockMessage:
    def __init__(
        self,
        author,
        channel,
        content,
        mentions=None,
        channel_mentions=None,
        attachments=None,
    ):
        self.author = author
        self.guild = channel.guild
        self.channel = channel
        self.content = content
        self.mentions = mentions or []
        self.channel_mentions = channel_mentions or []
        self.attachments = attachments or []
        self.reactions = set()
        if isinstance(channel, MockDM):
            channel.recipient = author
        self.delete = AsyncMock()

    async def add_reaction(self, emoji):
        self.reactions.add(emoji)
