# Croma stock checking logic using Scrape.do API

import asyncio
import logging
from typing import Optional, Tuple
import httpx
from config import SCRAPE_DO_API_KEY, CROMA_BASE_URL

logger = logging.getLogger(__name__)


async def check_stock_scrapedo(sku: str, pincode: str) -> Tuple[bool, Optional[str], str]:
    """
    Check product stock on Croma using Scrape.do Premium API with stealth mode.
    
    Returns:
        Tuple of (is_in_stock, product_name, error_message)
    """
    if not SCRAPE_DO_API_KEY:
        return False, None, "Scrape.do API key not configured"
    
    # Construct the product URL for Croma
    # Croma product URLs typically follow this pattern
    product_url = f"{CROMA_BASE_URL}/search?text={sku}"
    
    # Scrape.do API endpoint with stealth mode enabled
    scrape_do_url = "https://api.scrape.do"
    
    params = {
        "token": SCRAPE_DO_API_KEY,
        "url": product_url,
        "stealth": "true",  # Enable stealth mode to bypass Akamai
        "render": "false",  # Set to true if JavaScript rendering is needed
        "mobile": "false",
        "premium": "true",  # Use premium proxies
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(scrape_do_url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Scrape.do API returned status {response.status_code}")
                return False, None, f"API error: Status {response.status_code}"
            
            html_content = response.text
            
            # Parse the HTML to check stock status
            is_in_stock, product_name = parse_croma_response(html_content, sku, pincode)
            
            if is_in_stock or product_name:
                return is_in_stock, product_name, ""
            else:
                # Product might not be found or out of stock
                return False, None, ""
                
    except httpx.TimeoutException:
        logger.error(f"Timeout checking stock for SKU {sku}")
        return False, None, "Request timeout"
    except httpx.RequestError as e:
        logger.error(f"Request error for SKU {sku}: {str(e)}")
        return False, None, f"Request error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error checking stock for SKU {sku}: {str(e)}")
        return False, None, f"Unexpected error: {str(e)}"


def parse_croma_response(html: str, sku: str, pincode: str) -> Tuple[bool, Optional[str]]:
    """
    Parse Croma HTML response to extract stock status and product name.
    
    This parser looks for common patterns in Croma's product pages.
    May need adjustment based on actual Croma website structure.
    
    Returns:
        Tuple of (is_in_stock, product_name)
    """
    from html.parser import HTMLParser
    
    class CromaStockParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_stock = False
            self.product_name = None
            self.found_sku = False
            self.current_tag = None
            self.current_class = ""
            self.text_buffer = ""
            self.in_product_name = False
            self.in_stock_indicator = False
            
            # Common classes/indicators for stock status on Croma
            self.stock_indicators = [
                "in stock", "available", "instock", "add to cart",
                "buy now", "available for delivery"
            ]
            self.out_of_stock_indicators = [
                "out of stock", "outofstock", "not available", 
                "currently unavailable", "sold out"
            ]
            self.product_name_classes = [
                "product-name", "product-title", "title", "name",
                "product-detail-name", "pd-name"
            ]
        
        def handle_starttag(self, tag, attrs):
            self.current_tag = tag
            attrs_dict = dict(attrs)
            self.current_class = attrs_dict.get('class', '').lower()
            
            # Check for product name containers
            for name_class in self.product_name_classes:
                if name_class in self.current_class:
                    self.in_product_name = True
                    break
            
            # Check for stock-related elements
            if any(indicator in self.current_class for indicator in self.stock_indicators):
                self.in_stock_indicator = True
                self.in_stock = True
            
            if any(indicator in self.current_class for indicator in self.out_of_stock_indicators):
                self.in_stock_indicator = True
                self.in_stock = False
        
        def handle_endtag(self, tag):
            if self.in_product_name and self.text_buffer.strip():
                self.product_name = self.text_buffer.strip()[:100]  # Limit length
            self.in_product_name = False
            self.in_stock_indicator = False
            self.text_buffer = ""
        
        def handle_data(self, data):
            text_lower = data.lower().strip()
            
            # Capture product name
            if self.in_product_name:
                self.text_buffer += data
            
            # Check for stock indicators in text
            if any(indicator in text_lower for indicator in self.stock_indicators):
                self.in_stock = True
            
            if any(indicator in text_lower for indicator in self.out_of_stock_indicators):
                self.in_stock = False
            
            # Look for SKU in the page
            if sku.lower() in text_lower:
                self.found_sku = True
    
    parser = CromaStockParser()
    
    try:
        parser.feed(html)
    except Exception as e:
        logger.warning(f"Error parsing HTML: {str(e)}")
        return False, None
    
    # If we found the product name but couldn't determine stock,
    # assume it's available (conservative approach)
    if parser.product_name and not parser.found_sku:
        # Try to find stock status using regex patterns as fallback
        import re
        
        # Look for common stock patterns
        in_stock_patterns = [
            r'in\s*stock', r'available', r'instock',
            r'add\s*to\s*cart', r'buy\s*now'
        ]
        out_of_stock_patterns = [
            r'out\s*of\s*stock', r'outofstock', r'not\s*available',
            r'unavailable', r'sold\s*out'
        ]
        
        html_lower = html.lower()
        
        # Check for out of stock first (more specific)
        for pattern in out_of_stock_patterns:
            if re.search(pattern, html_lower):
                return False, parser.product_name
        
        # Check for in stock
        for pattern in in_stock_patterns:
            if re.search(pattern, html_lower):
                return True, parser.product_name
    
    return parser.in_stock, parser.product_name


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
