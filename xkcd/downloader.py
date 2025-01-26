import asyncio
import os
import re
import sys
from datetime import datetime
from typing import Optional
import aiohttp
from aiohttp import ClientSession
from zlog import FormattedStream, JSONFormatter, Logger
from tqdm import tqdm

# Set some globals
current_dir = os.path.dirname(os.path.realpath(__file__))
logger = Logger()

# Pretty print logs
logger.formatted_streams = [FormattedStream(JSONFormatter(2), sys.stdout)]


async def get_comic_data(session: ClientSession, comic_number: int) -> Optional[dict]:
    """Get comic metadata."""
    url = f"http://xkcd.com/{comic_number}/info.0.json"
    response = await session.get(url)

    try:
        return await response.json()
    except Exception as e:
        logger.error().exception("error", e).int("status_code", response.status).int(
            "comic_number", comic_number
        ).msg("Couldn't get data")
        return None

async def get_most_recent_comic_date_and_number(session:ClientSession) -> (datetime, int):
    """Get metadata about the most recent comic, so we know when to stop iterdting."""
    url = f"http://xkcd.com/info.0.json"
    response = await session.get(url)

    try:
        comic_data = await response.json()
    except Exception as e:
        logger.error().exception("error", e).int("status_code", response.status
        ).msg("Couldn't get data for most recent comic")
        raise e

    return (datetime(
        year=int(comic_data.get("year")),
        month=int(comic_data.get("month")),
        day=int(comic_data.get("day")),
    ), comic_data.get("num"))




def output_dir(comic_data: dict) -> str:
    """Create the output directory if it doesn't exist, and return as string."""
    year = comic_data.get("year")
    _output_dir = f"{current_dir}/comics/{year}"

    if not os.path.exists(_output_dir):
        os.mkdir(_output_dir)

    return _output_dir


async def download_comic(session: ClientSession, comic_data: dict) -> None:
    """Use comic metadata to download a comic."""
    year = comic_data.get("year")
    month = comic_data.get("month").zfill(2)
    day = comic_data.get("day").zfill(2)

    # Clean up title
    safe_title = re.sub(r"/|\\|\:|\*|\?|\"|<|>|\|", "", comic_data.get("safe_title"))
    img_url = comic_data.get("img")

    # Make output path
    comic_output_dir = output_dir(comic_data)
    extension = img_url.split(".")[-1]
    filename = f"({year}-{month}-{day}) {safe_title}.{extension}"
    output_path = f"{comic_output_dir}/{filename}"

    # Only download if extension is .png, .jpg, .jpeg
    if extension not in ["png", "jpg", "jpeg", "gif"]:
        logger.warn().int("comit_number", comic_data.get("num")).msg(f"Unexpected extension type: '.{extension}'. Skipping comic.")
        return

    # Only download if file does not exist already
    if not os.path.exists(output_path):
        try:
            # Download comic
            response = await session.get(img_url)
            file_content = await response.content.read()
        except Exception as e:
            logger.error().exception("error", e).dict("comic_data", comic_data).msg(
                "Couldn't save image."
            )
            return

        # Write data to output file
        with open(output_path, "wb") as f:
            f.write(file_content)
        return


async def main():
    async with aiohttp.ClientSession() as session:

        # Initialise while loop
        comic_date = datetime(2000, 1, 1)
        comic_number = 0

        most_recent_comic_date, most_recent_comic_number = await get_most_recent_comic_date_and_number(session)
        logger.info().int("Latest comic number", most_recent_comic_number).string("Latest comic date", most_recent_comic_date.strftime("%Y-%m-%d")).send()
        print("\nBeginning download...\n")

        pbar = tqdm(total = most_recent_comic_number - comic_number, unit= "comics", desc= "Downloading comics...")
        while comic_date < most_recent_comic_date:
            # Get next comic data
            comic_number += 1
            comic_data = await get_comic_data(session, comic_number)

            # Start next iteration if there is no metadata/metadata indicates non-comic comic
            if not comic_data or not comic_data.get("img"):
                logger.warn().dict("comic_data", comic_data).msg(
                    "Skipping non-comic comic..."
                )
                continue

            await download_comic(session, comic_data)

            # Set last comic date
            comic_date = datetime(
                year=int(comic_data.get("year")),
                month=int(comic_data.get("month")),
                day=int(comic_data.get("day")),
            )
            pbar.update(1)

        pbar.close()
        print("\nDownload complete!\n")



if __name__ == "__main__":
    asyncio.run(main())
