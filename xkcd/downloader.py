import asyncio
import re
from datetime import datetime

import aiohttp
import os

from aiohttp import ClientSession, ClientResponseError
from zlog import Logger

# Set some globals
current_dir = os.path.dirname(os.path.realpath(__file__))
logger = Logger()

async def get_comic_data(session: ClientSession, comic_number: int) -> dict:
    """Get comic metadata."""
    url = f"http://xkcd.com/{comic_number}/info.0.json"
    response = await session.get(url)
    try:
        return await response.json()
    except ClientResponseError as e:
        logger.error().exception("error", e).int("status_code", response.status).int("comic_number", comic_number).msg("Couldn't get data")


def output_dir(comic_data: dict) -> str:
    """Create the output directory if it doesn't exist, and return as string."""
    year = comic_data.get("year")
    _output_dir = f"{current_dir}/comics/{year}"

    if not os.path.exists(_output_dir):
        os.mkdir(_output_dir)

    return _output_dir


async def download_comic(session:ClientSession, comic_data: dict) -> None:
    """Use comic metadata to download a comic."""
    year = comic_data.get("year")
    month = comic_data.get("month")
    day = comic_data.get("day")

    # Clean up title
    safe_title = re.sub(r"/|\\|\:|\*|\?|\"|<|>|\|", "", comic_data.get("safe_title"))

    img_url = comic_data.get("img")

    # Make output path
    comic_output_dir = output_dir(comic_data)
    extension = img_url.split(".")[-1]
    filename = f"({year}-{month}-{day}) {safe_title}.{extension}"
    output_path = f"{comic_output_dir}/{filename}"

    # Only download if extension is .png, .jpg, .jpeg
    if extension not in ["png", "jpg", "jpeg"]:
        logger.warn().msg(f"Unexpected extension type: '.{extension}'. Skipping comic.")
        return

    # Only download if file does not exist already
    if not os.path.exists(output_path):
        try:
            # Download comic
            response = await session.get(img_url)
            file_content = await response.content.read()
        except Exception as e:
            logger.error().exception("error", e).dict("comic_data", comic_data).msg("Couldn't save image.")
            return

        # Write data to output file
        with open(output_path, "wb") as f:
            f.write(file_content)
        return

async def main():
    async with aiohttp.ClientSession() as session:
        # Initialise while loop
        comic_date=datetime(2000,1,1)
        comic_number = 1

        # Don't iterate forever...
        while comic_date < datetime.today():
            comic_data = await get_comic_data(session, comic_number)

            # Start next iteration if there is no metadata
            if not comic_data:
                continue

            # Start next iteration if metadata indicates non-comic comic
            if comic_data.get("extra_parts"):
                logger.warn().dict("comic_data", comic_data).msg("Skipping non-comic comic...")
                continue

            await download_comic(session, comic_data)

            # Loopy goodness
            comic_date = datetime(year=int(comic_data.get("year")), month=int(comic_data.get("month")), day=int(comic_data.get("day")))
            comic_number +=1



if __name__ == '__main__':
    asyncio.run(main())
