#!/usr/bin/env python3

import sys
from datetime import datetime, timedelta

from faker import Faker  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from spellbot.data import Channel, Game, Server, Tag, User, games_tags

url: str = sys.argv[1]
fake = Faker("en_US")

engine: Engine = create_engine(url)
conn: Connection = engine.connect()
make_session = sessionmaker(bind=engine)
session: Session = make_session()

n_tags = 500
tag_words = fake.words(nb=n_tags, unique=True)
tags = [Tag(id=i + 1, name=word.lower()) for i, word in enumerate(tag_words)]
session.bulk_save_objects(tags)
session.commit()

n_servers = 200
servers = [Server(guild_xid=i) for i in range(1, n_servers)]
session.bulk_save_objects(servers)
session.commit()

n_channels = 10 * n_servers
channels = [
    Channel(channel_xid=i, guild_xid=fake.random_int(min=1, max=n_servers - 1))
    for i in range(1, n_channels)
]
session.bulk_save_objects(channels)
session.commit()

now = datetime.utcnow()
n_games = 40 * n_servers
games = [
    Game(
        id=i,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=30),
        size=fake.random_int(min=2, max=4),
        guild_xid=fake.random_int(min=1, max=n_servers - 1),
        channel_xid=fake.random_int(min=10000, max=50000),
        url=None,
        status="pending",
        message=None,
        event_id=None,
        message_xid=fake.random_int(min=100000, max=500000),
        system="spelltable",
    )
    for i in range(1, n_games)
]
session.bulk_save_objects(games)
session.commit()

n_users = 1000
users = [
    User(
        xid=i,
        cached_name=fake.first_name(),
        game_id=fake.random_int(min=1, max=n_games - 1)
        if fake.random_int(min=0, max=1)
        else None,
    )
    for i in range(1, n_users)
]
session.bulk_save_objects(users)
session.commit()

games_tags_associations = []
for game_id in range(1, n_games):
    random_tags = fake.random_elements(elements=tags, length=5, unique=True)
    tag_count = fake.random_int(min=0, max=5)
    for tag in random_tags[0:tag_count]:
        games_tags_associations.append({"game_id": game_id, "tag_id": tag.id})
session.execute(games_tags.insert(), games_tags_associations)
session.commit()

if url.startswith("postgresql:"):
    # make sure that autoincrement is setup correctly
    session.execute("SELECT setval('tags_id_seq', MAX(id)) FROM tags;")
    session.execute("SELECT setval('games_id_seq', MAX(id)) FROM games;")
