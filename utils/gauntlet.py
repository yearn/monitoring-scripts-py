import requests
import re
from datetime import datetime, timedelta

def get_gauntlet_build_id():
    """Get the latest build ID from Gauntlet dashboard"""
    try:
        # Request the main page first to get the latest build ID
        response = requests.get("https://dashboards.gauntlet.xyz/")
        response.raise_for_status()

        # Find the build ID in the HTML
        # It's usually in a script tag with id="__NEXT_DATA__"
        build_id = re.search(r'"buildId":"([^"]+)"', response.text)
        if build_id:
            return build_id.group(1)
    except Exception as e:
        print(f"🚨 Error fetching Gauntlet build ID: {str(e)}")
    return None


def get_markets_for_protocol(protocol, max_retries=3):
    base_url = "https://dashboards.gauntlet.xyz/_next/data/{}/protocols/{}.json?protocolSlug={}"

    for attempt in range(max_retries):
        try:
            # Get the latest build ID
            build_id = get_gauntlet_build_id()
            if not build_id:
                # or return []
                raise Exception("Failed to get build ID")

            # Construct the URL with the latest build ID
            protocol_lower = protocol.lower()
            urlHealthMetrics = base_url.format(build_id, protocol_lower, protocol_lower)

            response = requests.get(urlHealthMetrics)
            response.raise_for_status()
            data = response.json()

            # If we get here, the request was successful
            # Continue with the existing logic
            markets = data["pageProps"]["protocolPage"]["markets"]
            return markets

        except requests.RequestException as e:
            if attempt == max_retries - 1:  # Last attempt
                print(
                    f"🚨 Error fetching Gauntlet metrics after {max_retries} attempts: {str(e)}"
                )
                return []
            print(f"Attempt {attempt + 1} failed, retrying...")
            continue
        except ValueError as e:
            print(f"🚨 Error parsing Gauntlet JSON response: {str(e)}")
            return []
        except Exception as e:
            print(f"🚨 Unexpected error: {str(e)}")
            return []


def get_timestamp_before(hours: int):
    """Get timestamp from one hour ago in ISO format"""
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=hours)
    return one_hour_ago.strftime("%Y-%m-%dT%H:00:00.000Z")


def format_usd(number: float) -> str:
    """Format number to readable USD string with K, M, B suffixes"""
    if number >= 1_000_000_000:
        return f"${number/1_000_000_000:.2f}B"
    if number >= 1_000_000:
        return f"${number/1_000_000:.2f}M"
    if number >= 1_000:
        return f"${number/1_000:.2f}K"
    return f"${number:.2f}"
