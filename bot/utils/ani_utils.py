from datetime import datetime

import flag
import humanize
from aiohttp_retry import ExponentialRetry, RetryClient

from bot import bot

from .bot_utils import post_to_tgph
from .log_utils import log

url = "https://graphql.anilist.co"

anime_query = """
query ($id: Int, $idMal:Int, $search: String, $type: MediaType, $asHtml: Boolean) {
  Media (id: $id, idMal: $idMal, search: $search, type: $type) {
    id
    idMal
    title {
      romaji
      english
      native
    }
    format
    status
    description (asHtml: $asHtml)
    startDate {
      year
      month
      day
    }
    season
    episodes
    duration
    countryOfOrigin
    source (version: 2)
    trailer {
      id
      site
      thumbnail
    }
    coverImage {
      extraLarge
    }
    bannerImage
    genres
    averageScore
    nextAiringEpisode {
      airingAt
      timeUntilAiring
      episode
    }
    isAdult
    characters (role: MAIN, page: 1, perPage: 10) {
      nodes {
        id
        name {
          full
          native
        }
        image {
          large
        }
        description (asHtml: $asHtml)
        siteUrl
      }
    }
    studios (isMain: true) {
      nodes {
        name
        siteUrl
      }
    }
    siteUrl
  }
}
"""


airing_query = """
query ($id: Int, $mediaId: Int, $notYetAired: Boolean) {
  Page(page: 1, perPage: 50) {
    airingSchedules (id: $id, mediaId: $mediaId, notYetAired: $notYetAired) {
      id
      airingAt
      timeUntilAiring
      episode
      mediaId
      media {
        title {
          romaji
          english
          native
        }
        duration
        coverImage {
          extraLarge
        }
        nextAiringEpisode {
          airingAt
          timeUntilAiring
          episode
        }
        bannerImage
        averageScore
        siteUrl
      }
    }
  }
}
"""


async def get_ani_info(title=None, query=anime_query, var=None):
    variables = var or {"search": title, "type": "ANIME"}
    retry_options = ExponentialRetry(attempts=10)
    retry_requests = RetryClient(bot.requests)
    result = await retry_requests.post(
        url, json={"query": query, "variables": variables}
    )
    if var:
        return await result.json()
    info = (await result.json())["data"].get("Media")
    return info


# Default templates for Query Formatting
# https://github.com/UsergeTeam/Userge-Plugins/blob/dev/plugins/utils/anilist/__main__.py
ANIME_TEMPLATE = """[{c_flag}] *{romaji}*

*ID | MAL ID:* {idm} | {idmal}
➤ *SOURCE:* {source}
➤ *TYPE:* {formats}
➤ *GENRES:* {genre}
➤ *SEASON:* {season}
➤ *EPISODES:* {episodes}
➤ *STATUS:* {status}
➤ *NEXT AIRING:* {air_on}
➤ *SCORE:* {score}% 🌟
➤ *ADULT RATED:* {adult}
🎬 {trailer_link}
📖 *Synopsis & More:* {synopsis_link}"""


def make_it_rw(time_stamp, as_countdown=False):
    """Converting Time Stamp to Readable Format"""
    if as_countdown:
        now = datetime.now()
        air_time = datetime.fromtimestamp(time_stamp)
        return str(humanize.naturaltime(now - air_time))
    return str(humanize.naturaldate(datetime.fromtimestamp(time_stamp)))


async def anime_arch(query, arg):
    """Search Anime Info"""
    vars_ = {"search": query, "asHtml": True, "type": "ANIME"}
    if query.isdigit():
        if arg.m:
            vars_ = {"idMal": int(query), "asHtml": True, "type": "ANIME"}
        else:
            vars_ = {"id": int(query), "asHtml": True, "type": "ANIME"}

    result = await get_ani_info(query=anime_query, var=vars_)
    error = result.get("errors")
    if error:
        log(e=f"*ANILIST RETURNED FOLLOWING ERROR:*\n\n{error}")
        error_sts = error[0].get("message")
        raise Exception(f"[{error_sts}]")

    data = result["data"]["Media"]
    # Data of all fields in returned json
    # pylint: disable=possibly-unused-variable
    idm = data.get("id")
    idmal = data.get("idMal")
    romaji = data["title"]["romaji"]
    english = data["title"]["english"]
    native = data["title"]["native"]
    formats = data.get("format")
    status = data.get("status")
    synopsis = data.get("description")
    season = data.get("season")
    episodes = data.get("episodes")
    duration = data.get("duration")
    country = data.get("countryOfOrigin")
    c_flag = flag.flag(country)
    source = data.get("source")
    coverImg = data.get("coverImage")["extraLarge"]
    bannerImg = data.get("bannerImage")
    genres = data.get("genres")
    genre = genres[0] if genres else genres
    if genre and len(genres) > 1:
        genre = ", ".join(genres)
    score = data.get("averageScore")
    air_on = None
    if data["nextAiringEpisode"]:
        nextAir = data["nextAiringEpisode"]["airingAt"]
        air_on = make_it_rw(nextAir)
    s_date = data.get("startDate")
    adult = data.get("isAdult")
    trailer_link = "N/A"

    if data["trailer"] and data["trailer"]["site"] == "youtube":
        trailer_link = f"*Trailer:* https://youtu.be/{data['trailer']['id']}"
    html_char = ""
    for character in data["characters"]["nodes"]:
        html_ = ""
        html_ += "<br>"
        html_ += f"""<a href="{character['siteUrl']}">"""
        html_ += f"""<img src="{character['image']['large']}"/></a>"""
        html_ += "<br>"
        html_ += f"<h3>{character['name']['full']}</h3>"
        html_ += f"<em>{c_flag} {character['name']['native']}</em><br>"
        html_ += f"<b>Character ID</b>: {character['id']}<br>"
        html_ += (
            f"<h4>About Character and Role:</h4>{character.get('description', 'N/A')}"
        )
        html_char += f"{html_}<br><br>"

    studios = ""
    for studio in data["studios"]["nodes"]:
        studios += "<a href='{}'>• {}</a> ".format(studio["siteUrl"], studio["name"])
    url = data.get("siteUrl")

    title_img = coverImg or bannerImg
    html_pc = ""
    html_pc += f"<img src='{title_img}' title={romaji}/>"
    html_pc += f"<h1>[{c_flag}] {native}</h1>"
    html_pc += "<h3>Synopsis:</h3>"
    html_pc += synopsis
    html_pc += "<br>"
    if html_char:
        html_pc += "<h2>Main Characters:</h2>"
        html_pc += html_char
        html_pc += "<br><br>"
    html_pc += "<h3>More Info:</h3>"
    html_pc += f"<b>Started On:</b> {s_date['day']}/{s_date['month']}/{s_date['year']}"
    html_pc += f"<br><b>Studios:</b> {studios}<br>"
    html_pc += f"<a href='https://myanimelist.net/anime/{idmal}'>View on MAL</a>"
    html_pc += f"<a href='{url}'> View on anilist.co</a>"
    html_pc += f"<img src='{bannerImg}'/>"

    title_h = english or romaji
    synopsis_link = (await post_to_tgph(title_h, html_pc))["url"]
    finals_ = ANIME_TEMPLATE.format(**locals())
    return title_img, finals_


async def airing_anim(query):
    """Get Airing Detail of Anime"""
    vars_ = {"search": query, "asHtml": True, "type": "ANIME"}
    if query.isdigit():
        vars_ = {"id": int(query), "asHtml": True, "type": "ANIME"}
    result = await get_ani_info(query=anime_query, var=vars_)
    error = result.get("errors")
    if error:
        log(e=f"*ANILIST RETURNED FOLLOWING ERROR:*\n\n{error}")
        error_sts = error[0].get("message")
        raise Exception(f"[{error_sts}]")

    data = result["data"]["Media"]

    # Airing Details
    mid = data.get("id")
    romaji = data["title"]["romaji"]
    english = data["title"]["english"]
    native = data["title"]["native"]
    status = data.get("status")
    episodes = data.get("episodes")
    country = data.get("countryOfOrigin")
    c_flag = flag.flag(country)
    source = data.get("source")
    coverImg = data.get("coverImage")["extraLarge"]
    genres = data.get("genres")
    genres = data.get("genres")
    genre = genres[0] if genres else genres
    if genre and len(genres) > 1:
        genre = ", ".join(genres)
    score = data.get("averageScore")
    air_on = None
    if data["nextAiringEpisode"]:
        nextAir = data["nextAiringEpisode"]["airingAt"]
        episode = data["nextAiringEpisode"]["episode"]
        air_on = make_it_rw(nextAir, True)

    title_ = english or romaji
    out = f"[{c_flag}] *{native}* \n   ({title_})"
    out += f"\n\n*ID:* {mid}"
    out += f"\n*Status:* {status}\n"
    out += f"*Source:* {source}\n"
    out += f"*Score:* {score}\n"
    out += f"*Genres:* {genre}\n"
    if air_on:
        out += f"*Airing Episode:* [{episode}/{episodes}]\n"
        out += f"\n{air_on}"
    return coverImg, out
