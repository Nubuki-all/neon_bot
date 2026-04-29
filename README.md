# neon_bot

A feature-rich WhatsApp bot built with the [neonize](https://github.com/Nubuki-all/neonize) library, designed to provide media downloading, group management, image processing, and fun utilities.

## Features

### 📥 Media Downloaders
- **YouTube & Universal Downloader**: Download videos from YouTube and other supported sites.
- **Instagram Downloader**: High-quality downloads for Instagram Posts, Reels, Stories, and IGTV.
- **Video Trimming**: Trim videos during download using bracketed arguments (e.g., `[00:10-00:20]`).

### 🎨 Sticker & Image Tools
- **Sticker Creation**: Convert images, videos, and GIFs into stickers.
- **Sticker to Image**: Convert stickers back into images or GIFs.
- **Image Upscaling**: Enhance image quality using Real-ESRGAN.
- **Sticker Kanging**: Rename sticker metadata to your own pack name.

### 👥 Group Management
- **Greetings**: Set custom welcome and goodbye messages for group members.
- **Rules**: Set and retrieve group rules.
- **Message Ranking**: Track message statistics and view group leaderboards (🥇, 🥈, 🥉).
- **Roles**: Create and manage custom roles within the group for easy tagging.
- **Filters**: Set automatic responses for specific keywords.
- **Notes**: Save and retrieve frequently used text or media.
- **Undelete**: Retrieve deleted messages in a group.

### 🎉 Fun & Entertainment
- **Random Media**: Fetch random cat/dog pictures and videos.
- **Coub**: Get short, looping videos from Coub.
- **GIFs & Memes**: Search for and send GIFs and memes.
- **Anime**: Fetch anime info and airing schedules from AniList.

### 🛠 Utilities
- **AFK**: Set an AFK status to notify others when you are away.
- **RSS Feeds**: Subscribe to RSS feeds and receive updates in your chats.
- **Screenshot**: Generate screenshots of websites from a URL.
- **URL Sanitization**: Clean and sanitize tracking parameters from links.
- **Dev Tools**: Integrated `eval` and `bash` commands for developers.

## Commands

### General Commands
- `.ping`: Check bot latency and uptime.
- `.cmds`: List available modules and basic help.
- `.tools`: Show help for group management and utility tools.
- `.fun`: Show help for entertainment features.
- `.roles`: Manage and list group roles.
- `.anime [query]`: Search for anime info.
- `.airing [query]`: Check anime airing schedule.

### Group Management
- `.greetings [on/off]`: Enable or disable welcome/goodbye messages.
- `.setwelcome`: Set a custom welcome message (Reply to message).
- `.unsetwelcome`: Remove the custom welcome message.
- `.setrules`: Set group rules (Reply to text).
- `.rules`: View group rules in PM.
- `.msg_ranking`: View the group message leaderboard.
- `.save [name]`: Save a replied message as a note.
- `.get [name]`: Retrieve a saved note.
- `.filter [word]`: Create a keyword filter (Reply to message).

### Media & Tools
- `.sticker`: Convert replied media to a sticker.
- `.stick2img`: Convert a sticker back to its original format.
- `.upscale`: Upscale a replied image.
- `.mp3`: Convert a replied video to audio.
- `.screenshot [url]`: Take a screenshot of the specified website.

## Configuration

The bot can be configured via environment variables or a `.env` file. Key variables include:

- `PH_NUMBER`: Your WhatsApp phone number (with country code, without `+`).
- `CMD_PREFIX`: Command prefix (e.g., `.`).
- `OWNER`: Phone number of the bot owner (with country code, without `+`).
- `SUDO`: Phone numbers of sudo users (comma-separated, without `+`).
- `ALLOWED_CHATS`: Numeric IDs of chats where the bot is allowed to operate (comma-separated).
- `DATABASE_URL`: MongoDB connection string.
- `WA_DB`: Path to the WhatsApp session database (e.g., `db.sqlite3`).
- `BLOCK_NSFW`: Enable/disable NSFW filtering (Default: `True`).

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