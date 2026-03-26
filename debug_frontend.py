 import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sys

def debug_web_assets(base_url):
    print(f"--- Debugging Assets for: {base_url} ---")
    
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching base URL: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1. Check for <base> tag
    base_tag = soup.find('base')
    if base_tag:
        print(f"[BASE TAG FOUND]: {base_tag.get('href')}")
    else:
        print("[BASE TAG MISSING]")

    # 2. Collect assets
    assets = []
    for tag in soup.find_all(['script', 'link', 'img']):
        attr = 'src' if tag.name in ['script', 'img'] else 'href'
        val = tag.get(attr)
        if val:
            assets.append((tag.name, val))

    print(f"\nFound {len(assets)} potential assets. Testing reachability...\n")
    print(f"{'Type':<10} | {'Status':<8} | {'Original Path':<50} | {'Resolved URL'}")
    print("-" * 120)

    for tag_name, path in assets:
        # Resolve path
        resolved_url = urljoin(base_url, path)
        
        try:
            # We use HEAD first to be quick, fallback to GET if HEAD not allowed
            res = requests.head(resolved_url, timeout=5, allow_redirects=True)
            if res.status_code == 405: # Method Not Allowed
                res = requests.get(resolved_url, timeout=5, stream=True)
            
            status = res.status_code
        except Exception as e:
            status = f"ERR: {type(e).__name__}"

        print(f"{tag_name:<10} | {status:<8} | {path:<50} | {resolved_url}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://test-cosmichorizon-worker-68a3110f01feebd0.elb.us-gov-west-1.amazonaws.com/ai-websearch/"
    
    debug_web_assets(url)
