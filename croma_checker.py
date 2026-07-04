# Croma stock checking logic using Scrape.do API

import asyncio
import logging
from typing import Optional, Tuple
import httpx
from config import SCRAPE_DO_API_KEY

logger = logging.getLogger(__name__)

# Croma API endpoint
CROMA_API_URL = "https://www.croma.com/api/v1/product/availability"


async def check_stock_scrapedo(sku: str, pincode: str, retry_count: int = 0) -> Tuple[bool, Optional[str], str]:
    """
    Check product stock on Croma using Scrape.do Premium API with stealth mode.
    
    Args:
        sku: Product SKU
        pincode: Delivery pincode
        retry_count: Current retry attempt (internal use)
    
    Returns:
        Tuple of (is_in_stock, product_name, error_message)
    """
    if not SCRAPE_DO_API_KEY:
        return False, None, "Scrape.do API key not configured"
    
    # Direct API endpoint with params
    product_url = f"{CROMA_API_URL}?sku={sku}&pincode={pincode}"
    
    # Scrape.do API endpoint with ALL premium parameters
    scrape_do_url = "https://api.scrape.do"
    
    params = {
        "token": SCRAPE_DO_API_KEY,
        "url": product_url,
        "stealth": "true",           # Bypass Akamai
        "render": "true",            # Enable browser rendering
        "residential": "true",       # Use Indian residential IP
        "geo": "IN",                 # India location
        "block_ads": "true",         # Block ads/trackers
        "wait_for": "networkidle",   # Wait for page to load
        "timeout": "60",             # 60 seconds timeout
        "mobile": "true",            # Mobile mode
        "premium": "true",           # Premium proxies
    }
    
    # Mobile Android headers (less suspicious)
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "sec-ch-ua": '"Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "Referer": "https://www.croma.com/",
        "Connection": "keep-alive",
    }
    
    try:
        async with httpx.AsyncClient(timeout=65.0, follow_redirects=True) as client:
            response = await client.get(scrape_do_url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Scrape.do API returned status {response.status_code}")
                
                # Retry logic
                if retry_count < 3:
                    wait_time = 5 * (2 ** retry_count)  # 5s, 10s, 20s
                    logger.info(f"Retrying in {wait_time}s (attempt {retry_count + 1}/3)")
                    await asyncio.sleep(wait_time)
                    return await check_stock_scrapedo(sku, pincode, retry_count + 1)
                
                return False, None, f"API error: Status {response.status_code}"
            
            # Parse JSON response
            try:
                data = response.json()
                return parse_croma_json_response(data, sku)
            except Exception as e:
                logger.error(f"JSON parse error: {str(e)}")
                return False, None, f"JSON parse error: {str(e)}"
                
    except httpx.TimeoutException:
        logger.error(f"Timeout checking stock for SKU {sku}")
        if retry_count < 3:
            wait_time = 5 * (2 ** retry_count)
            await asyncio.sleep(wait_time)
            return await check_stock_scrapedo(sku, pincode, retry_count + 1)
        return False, None, "Request timeout"
        
    except httpx.RequestError as e:
        logger.error(f"Request error for SKU {sku}: {str(e)}")
        if retry_count < 3:
            wait_time = 5 * (2 ** retry_count)
            await asyncio.sleep(wait_time)
            return await check_stock_scrapedo(sku, pincode, retry_count + 1)
        return False, None, f"Request error: {str(e)}"
        
    except Exception as e:
        logger.error(f"Unexpected error checking stock for SKU {sku}: {str(e)}")
        if retry_count < 3:
            wait_time = 5 * (2 ** retry_count)
            await asyncio.sleep(wait_time)
            return await check_stock_scrapedo(sku, pincode, retry_count + 1)
        return False, None, f"Unexpected error: {str(e)}"


def parse_croma_json_response(data: dict, sku: str) -> Tuple[bool, Optional[str], str]:
    """
    Parse Croma JSON API response to extract stock status.
    
    Returns:
        Tuple of (is_in_stock, product_name, error_message)
    """
    try:
        # Extract availability status
        availability_status = data.get("availabilityStatus", "").upper()
        
        # Extract product name if available
        product_name = data.get("productName") or data.get("title") or data.get("name")
        
        # Check if in stock
        is_in_stock = any(keyword in availability_status for keyword in ["AVAILABLE", "IN_STOCK"])
        
        if is_in_stock:
            return True, product_name, ""
        else:
            return False, product_name, ""
            
    except Exception as e:
        logger.error(f"Error parsing response: {str(e)}")
        return False, None, f"Parse error: {str(e)}"


async def check_multiple_products(products: list) -> list:
    """
    Check stock for multiple products concurrently.
    
    Args:
        products: List of dicts with 'id', 'sku', 'pincode' keys
    
    Returns:
        List of results with updated stock information
    """
    tasks = []
    for product in products:
        task = check_stock_scrapedo(product['sku'], product['pincode'])
        tasks.append((product, task))
    
    results = []
    for product, task in tasks:
        try:
            is_in_stock, product_name, error = await task
            results.append({
                'product': product,
                'is_in_stock': is_in_stock,
                'product_name': product_name,
                'error': error
            })
        except Exception as e:
            logger.error(f"Error checking product {product['sku']}: {str(e)}")
            results.append({
                'product': product,
                'is_in_stock': False,
                'product_name': None,
                'error': str(e)
            })
    
    return results
