import aiohttp
import asyncio


async def fetch(session, url):
    while True:
        async with session.get(url) as response:
            text = await response.text()
            print(text)
        await asyncio.sleep(5)


async def main():
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, 'http://python.org')
        print(html)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
