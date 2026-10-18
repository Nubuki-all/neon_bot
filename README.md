# neon_bot

A feature-rich WhatsApp bot built with the [neonize](https://github.com/Nubuki-all/neonize) library, designed to provide media downloading, group management, image processing, and fun utilities.

## Features

### 📥 Media Downloaders
- **Auto Downloader**: Send a link from YouTube, Instagram, TikTok, Twitter/X, Pinterest or any other [yt-dlp](https://github.com/yt-dlp/yt-dlp) supported site and the bot downloads and uploads it (enable per chat with `.ytdl_enable`).
  - Add `#no_ytdl` to a message to skip it, or `#yt-dlp-only` to force yt-dlp.
  - Trim videos during download using bracketed arguments (e.g., `[00:10-00:20]`).
- **TikTok**: Download TikTok videos with `.tikmate`.

### 🎞 Media Tools
- **Convert**: Video to audio, media to document, and documents back to media (add `(asm)` to a document's caption).
- **Compress**: Compress videos.
- **Inspect**: Get a video's FPS or full mediainfo.
- **Repair**: Make some unplayable videos playable.
- **Screenshot**: Generate screenshots of websites from a URL.

### 🎨 Sticker & Image Tools
- **Sticker Creation**: Convert images, videos, and GIFs into stickers.
- **Sticker to Image**: Convert stickers back into images or GIFs.
- **Sticker Kanging**: Rename sticker metadata to your own pack name.
- **Image Upscaling**: Enhance image quality using Real-ESRGAN, locally or through a Modal endpoint (single images or whole albums).

### 👥 Group Management
- **Greetings**: Custom welcome and goodbye messages for group members.
- **Rules**: Set group rules and send them to members in PM.
- **Roles**: Create custom roles that members can join, then tag the whole role at once.
- **Mass Tagging**: Tag everyone (`@all`/`@everyone`), admins (`@admins`/`@mods`), owners (`@owners`) or sudoers (`@sudoers`) in a message.
- **Filters**: Automatic responses for specific keywords.
- **Notes**: Save and retrieve frequently used text or media (`.get name` or `#name`).
- **Message Ranking**: Track message statistics with weekly leaderboards, or monthly ones that reset in the first week of each month (🥇, 🥈, 🥉).
- **Moderation**: Pin/unpin and purge messages, auto-delete messages from muted users, and auto-delete mass tags.
- **Undelete**: Retrieve deleted messages in a group.
- **Objection!**: Render a stretch of chat as an Ace Attorney style courtroom video.

### 🎉 Fun & Entertainment
- **Random Media**: Random cat/dog pictures and videos, and short looping videos from Coub.
- **GIFs, Stickers & Memes**: Search for GIFs and stickers, or fetch random memes from Reddit.
- **Anime**: Anime info and airing schedules from AniList.
- **Werewolf**: Play a game of Werewolf with your group.
- **Chatbot**: Chat with the bot in PM (requires `CHATBOT_DB`).

### 🛠 Utilities
- **AFK**: Set an AFK status; messages that tag or reply to you are forwarded to your DM.
- **Reminders**: Get tagged on a replied message at a specified time.
- **RSS Feeds**: Subscribe to RSS feeds and receive updates in your chats.
- **URL Sanitization**: Strip tracking parameters from links.
- **Random Choice**: Let the bot pick from a list of options.
- **Message Store**: Messages are stored locally (for undelete, objection, etc.) and cleaned up automatically after `MSG_STORE_STALE` seconds.

## Commands

The default command prefix is `.`; change it with `CMD_PREFIX`. Use `.cmds`, `.tools`, `.fun` and `.roles` in chat for the built-in help.

### General
- `.ping`: Check bot latency and uptime.
- `.cmds`: List available modules and basic help.
- `.tools`: Show help for group management and utility tools.
- `.fun`: Show help for entertainment features.
- `.gc_info`: Get the group chat's owner.
- `.afk [reason]`: Mark yourself as AFK.

### Media & Tools
- `.sticker`: Convert replied media to a sticker.
- `.stick2img`: Convert a sticker back to an image/GIF.
- `.kang`: Kang a replied sticker.
- `.upscale` / `.batch_upscale`: Upscale a replied image / album.
- `.mp3`: Convert a replied video to audio.
- `.doc`: Convert replied media to a document.
- `.compress`: Compress a replied video.
- `.fps` / `.mediainfo`: Get the FPS / mediainfo of a replied video.
- `.sanitize_video`: Make a replied video playable.
- `.tikmate [url]`: Download a TikTok video.
- `.screenshot [url]`: Take a screenshot of a website.
- `.sanitize [url]`: Sanitize a link or replied message.
- `.random [options]`: Pick a random choice.
- `.repeat`: Repeat a replied message.

### Notes, Filters & Reminders
- `.save [name]` / `.get [name]` / `.del_note [name]`: Save, get, or delete a note. `#name` also gets a note and `#notes` lists them.
- `.filter [word]` / `.filters` / `.del_filter [word]`: Create, list, or delete keyword filters.
- `.remindme [time]` / `.all_reminders` / `.del_reminder`: Set, list, or delete reminders.

### Group Management
- `.greetings [on/off]`: Enable or disable welcome/goodbye messages.
- `.setwelcome` / `.unsetwelcome`: Set or remove a custom welcome message.
- `.setrules` / `.delrules` / `.rules`: Set, delete, or view group rules.
- `.roles [-l | role_name]`: List role commands, list roles, or show a role.
- `.new_role` / `.edit_role` / `.del_role`: Create, edit, or delete a role.
- `.join_role` / `.exit_role`: Join or leave a role.
- `.add2role` / `.rm_from_role`: Add or remove users from a role.
- `.msg_ranking`: View the group message leaderboard.
- `.amr_enable [weekly/monthly]` / `.amr_disable`: Toggle automatic message ranking.
- `.pin` / `.unpin`: Pin or unpin a replied message.
- `.purge`: Mass delete messages.
- `.mute [-a/-rm/-c]`: Manage users whose messages are auto-deleted.
- `.enable_atd` / `.disable_atd`: Toggle auto-deleting mass tags.
- `.ytdl_enable` / `.ytdl_disable`: Toggle the auto downloader in a chat.
- `.enable` / `.disable`: Enable or disable bot replies in a group.
- `.undel`: Retrieve deleted messages.
- `.del`: Delete a replied bot message.
- `.insession` / `.renderobj`: Mark the start of an objection session / render it up to the replied message.

### Fun
- `.cat` / `.dog` / `.coub`: Random cat, dog, or Coub media.
- `.gif [query]` / `.gsticker [query]`: Random GIF or sticker from search results.
- `.meme [subreddit]`: Random meme.
- `.anime [query]` / `.airing [query]`: Anime info / airing schedule.
- `.werewolf [-j/-l/-s/--start]`: Join, leave, check, or start a Werewolf game.

### Owner & Dev
- `.sudo [-a/-rm/-c]`: Manage sudo users.
- `.ban` / `.unban`: Ban or unban a user from using the bot.
- `.pause [on/off]`: Make the bot ignore non-owners.
- `.rss`: Manage RSS feed subscriptions.
- `.update` / `.restart`: Update or restart the bot.
- `.logs`: Get the bot logs.
- `.eval [code]` / `.bash [cmd]`: Run Python code or shell commands.

## Configuration

The bot can be configured via environment variables or a `.env` file (see `.env.sample`). Don't use quotes around values, and separate multiple values with spaces.

### Required

| Variable | Description |
| --- | --- |
| `PH_NUMBER` | Your WhatsApp phone number (with country code, without `+`). |
| `OWNER` | Phone number(s) of the bot owner(s) (with country code, without `+`). |

### Optional

| Variable | Default | Description |
| --- | --- | --- |
| `ALLOWED_CHATS` | | IDs of chats where the bot is allowed to operate. |
| `ALWAYS_DEPLOY_LATEST` | `False` | Pull the latest code from upstream on every start. |
| `ALWAYS_UPDATE_PY_REQ` | `False` | Reinstall Python requirements on every update. |
| `BACKUP_WA_DB` | | Postgres URL to periodically back up `WA_DB` to (requires `WA_DB` to be a Postgres URL and the Postgres client tools). |
| `BANNED_USERS` | | Users the bot should ignore. |
| `BLOCK_NSFW` | `True` | Enable/disable NSFW filtering. |
| `CMD_PREFIX` | `.` | Command prefix. |
| `CHATBOT_DB` | | MongoDB URL for the chatbot; the chatbot is disabled if unset. |
| `DATABASE_URL` | | MongoDB connection string. |
| `DBNAME` | `Neon` | MongoDB database name. |
| `DB_ID` | `0000` | Database document ID, used when `PH_NUMBER` is not set. |
| `DEBUG` | `False` | Enable debug logging. |
| `DEV` | | Phone numbers of developers (allowed to use dev tools). |
| `DISABLE_CIP` | `False` | Disable CPU-intensive processes (local image upscaling). |
| `IGNORE_PM` | `True` | Ignore private messages. Has no effect if `ALLOWED_CHATS` is set. |
| `KLIPY_API_KEY` | | API key for GIF and meme search. |
| `LOG_GROUP` | | Chat ID to send logs and errors to (`id` or `id:server`). |
| `MODAL_UPSCALE_API` | | URL of a Modal upscaling endpoint. |
| `MODAL_UPSCALE_TOKEN` | | Token for `MODAL_UPSCALE_API`. |
| `MSG_STORE` | `sqlite+aiosqlite:///msg_store.db` | SQLAlchemy async URL of the local message store. |
| `MSG_STORE_STALE` | `2592000` | Seconds before stored messages are deleted (30 days); `0` disables cleanup. |
| `NO_GPU` | `False` | Don't use the GPU for upscaling even if one is available. |
| `RSS_CHAT` | | Default chat ID(s) to send RSS feed updates to. |
| `RSS_DELAY` | `60` | Seconds between RSS feed checks. |
| `TELEGRAPH_API` | `https://api.telegra.ph` | Telegraph API URL. |
| `UPSTREAM_BRANCH` | `main` | Branch to update from. |
| `UPSTREAM_REPO` | `https://github.com/Nubuki-all/neon_bot` | Repository to update from. |
| `WA_DB` | `db.sqlite3` | Path or URL of the WhatsApp session database. |
| `WA_DB_BACKUP_INTERVAL` | `43200` | Seconds between `WA_DB` backups. |

## Installation

### Standard Deployment

1.  Clone the repository:
    ```bash
    git clone https://github.com/Nubuki-all/neon_bot.git
    cd neon_bot
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Configure your environment variables in a `.env` file.
4.  Run the bot:
    ```bash
    bash run.sh
    ```

### Docker Deployment

1.  Build the Docker image:
    ```bash
    docker build -t neon_bot .
    ```
2.  Run the container:
    ```bash
    docker run -it --env-file .env neon_bot
    ```

## License

This project is licensed under the GNU General Public License v3. See the `LICENSE` file for details.