from mocks.discord import MockMember, MockRole  # type: ignore

CLIENT_USER = "ADMIN"
CLIENT_USER_ID = 82226367030108160

ADMIN_ROLE = MockRole("SpellBot Admin")
PLAYER_ROLE = MockRole("Player Player")

ADMIN = MockMember(CLIENT_USER, CLIENT_USER_ID, roles=[ADMIN_ROLE], admin=True)
FRIEND = MockMember("friend", 82169952898900001, roles=[PLAYER_ROLE])
BUDDY = MockMember("buddy", 82942320688700002, roles=[ADMIN_ROLE, PLAYER_ROLE])
GUY = MockMember("guy", 82988021019800003)
DUDE = MockMember("dude", 82988761019800004, roles=[ADMIN_ROLE])

JR = MockMember("J.R.", 72988021019800005)
ADAM = MockMember("Adam", 62988021019800006)
TOM = MockMember("Tom", 62988021019800016)
AMY = MockMember("Amy", 52988021019800007)
JACOB = MockMember("Jacob", 42988021019800008)

PUNK = MockMember("punk", 119678027792600009)  # for a memeber that's not in our channel
BOT = MockMember("robot", 82169567890900010)
BOT.bot = True
ADMIN.bot = True

SERVER_MEMBERS = [FRIEND, BUDDY, GUY, DUDE, ADMIN, JR, ADAM, TOM, AMY, JACOB]
ALL_USERS = []  # users that are on the server, setup in client fixture
