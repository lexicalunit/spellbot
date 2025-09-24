#!/usr/bin/env python3
from __future__ import annotations

from itertools import islice
from os.path import realpath
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict

import yaml

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Sequence

SRC_ROOT = Path(realpath(__file__)).parent.parent
SERVERS_FILE = SRC_ROOT / "conf" / "servers.yaml"
README_FILE = SRC_ROOT / "README.md"
INDEX_FILE = SRC_ROOT / "docs" / "index.html"


class Server(TypedDict):
    name: str  # server name
    url: str  # server url
    small: NotRequired[bool]  # server name should render with small font
    # server should have either a logo or both dark/light logos
    logo: NotRequired[str]  # server logo
    dark_logo: NotRequired[str]  # server logo for dark mode
    light_logo: NotRequired[str]  # server logo for light mode


def batched[T](iterable: Iterable[T], n: int) -> Generator[Sequence[T], None, None]:
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            return
        yield batch


def update_readme(servers: list[Server]) -> None:
    with README_FILE.open() as f:
        readme_text = f.read()
    lhs = readme_text.split("<!-- SERVERS BEGIN -->")[0]
    rhs = readme_text.split("<!-- SERVERS END -->")[1]
    with README_FILE.open("w") as f:
        f.write(lhs)
        f.write("<!-- SERVERS BEGIN -->\n")
        f.write("<table>\n")
        for batch in batched(servers, 3):
            f.write("    <tr>\n")
            for server in batch:
                logo = server.get("logo") or server.get("dark_logo")
                assert logo is not None
                name = server["name"]
                nbsp_name = name.replace(" ", "&nbsp;")
                url = server["url"]
                f.write(
                    "        "
                    '<td align="center">'
                    f'<a href="{url}">'
                    f'<img width="200" height="200" src="{logo}" alt="{name}" />'
                    "<br />"
                    f"{nbsp_name}"
                    "</a>"
                    "</td>\n",
                )
            f.write("    </tr>\n")
        f.write("</table>\n")
        f.write("<!-- SERVERS END -->")
        f.write(rhs)


def update_index(servers: list[Server]) -> None:
    with INDEX_FILE.open() as f:
        index_text = f.read()
    lhs = index_text.split("<!-- SERVERS BEGIN -->")[0]
    rhs = index_text.split("<!-- SERVERS END -->")[1]
    with INDEX_FILE.open("w") as f:
        f.write(lhs)
        f.write("<!-- SERVERS BEGIN -->\n")
        f.write('    <div class="where">\n')
        for server in servers:
            logo = server.get("logo") or server.get("light_logo")
            assert logo is not None
            name = server["name"]
            nbsp_name = name.replace(" ", "&nbsp;")
            if server.get("small") or False:
                nbsp_name = f'<span class="small">{nbsp_name}</span>'
            url = server["url"]
            f.write(
                "        "
                "<div>"
                f'<a href="{url}">'
                f'<img width="200" height="200" src="{logo}" alt="{name}" />'
                "<br />"
                f"{nbsp_name}"
                "</a>"
                "</div>\n",
            )
        f.write("    </div>\n")
        f.write("<!-- SERVERS END -->")
        f.write(rhs)


if __name__ == "__main__":
    with SERVERS_FILE.open() as f:
        servers_data = yaml.safe_load(f)
    servers = servers_data["servers"]
    update_readme(servers)
    update_index(servers)
