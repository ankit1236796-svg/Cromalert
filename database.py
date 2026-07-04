# Database module for SQLite user management

import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple
from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Users table for rate limiting
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            last_command_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tracked products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracked_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sku TEXT NOT NULL,
            pincode TEXT NOT NULL,
            product_name TEXT,
            is_in_stock BOOLEAN DEFAULT FALSE,
            last_checked TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, sku, pincode),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # Stock history for tracking changes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracked_product_id INTEGER,
            was_in_stock BOOLEAN,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tracked_product_id) REFERENCES tracked_products(id)
        )
    """)
    
    conn.commit()
    conn.close()


def add_user(user_id: int, username: str) -> bool:
    """Add a new user or update existing user info."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO users (user_id, username, last_command_time)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                username = excluded.username,
                last_command_time = excluded.last_command_time
        """, (user_id, username, datetime.now()))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()


def update_user_last_command(user_id: int) -> None:
    """Update the last command time for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users SET last_command_time = ? WHERE user_id = ?
    """, (datetime.now(), user_id))
    
    conn.commit()
    conn.close()


def get_user_last_command(user_id: int) -> Optional[datetime]:
    """Get the last command time for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_command_time FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['last_command_time']:
        return datetime.fromisoformat(row['last_command_time'])
    return None


def add_tracked_product(user_id: int, sku: str, pincode: str, product_name: str = None) -> Tuple[bool, str]:
    """Add a product to track. Returns (success, message)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if already tracking
        cursor.execute("""
            SELECT id FROM tracked_products 
            WHERE user_id = ? AND sku = ? AND pincode = ?
        """, (user_id, sku, pincode))
        
        if cursor.fetchone():
            return False, "You are already tracking this product with this pincode."
        
        # Check max limit
        cursor.execute("""
            SELECT COUNT(*) as count FROM tracked_products WHERE user_id = ?
        """, (user_id,))
        
        count = cursor.fetchone()['count']
        from config import MAX_TRACKED_PRODUCTS_PER_USER
        if count >= MAX_TRACKED_PRODUCTS_PER_USER:
            return False, f"You can track maximum {MAX_TRACKED_PRODUCTS_PER_USER} products."
        
        # Add the product
        cursor.execute("""
            INSERT INTO tracked_products (user_id, sku, pincode, product_name, last_checked)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, sku.upper(), pincode, product_name, datetime.now()))
        
        conn.commit()
        return True, f"Successfully added SKU {sku.upper()} to tracking list for pincode {pincode}."
    
    except sqlite3.Error as e:
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def remove_tracked_product(user_id: int, sku: str) -> Tuple[bool, str]:
    """Remove a product from tracking. Returns (success, message)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            DELETE FROM tracked_products 
            WHERE user_id = ? AND sku = ?
        """, (user_id, sku.upper()))
        
        if cursor.rowcount > 0:
            conn.commit()
            return True, f"Stopped tracking SKU {sku.upper()}."
        else:
            return False, f"SKU {sku.upper()} not found in your tracking list."
    
    except sqlite3.Error as e:
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def get_user_tracked_products(user_id: int) -> List[dict]:
    """Get all products tracked by a user."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, sku, pincode, product_name, is_in_stock, last_checked
        FROM tracked_products
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    
    products = []
    for row in cursor.fetchall():
        products.append({
            'id': row['id'],
            'sku': row['sku'],
            'pincode': row['pincode'],
            'product_name': row['product_name'],
            'is_in_stock': bool(row['is_in_stock']),
            'last_checked': row['last_checked']
        })
    
    conn.close()
    return products


def update_product_stock(product_id: int, is_in_stock: bool, product_name: str = None) -> None:
    """Update stock status for a product."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Update the product
        if product_name:
            cursor.execute("""
                UPDATE tracked_products 
                SET is_in_stock = ?, product_name = ?, last_checked = ?
                WHERE id = ?
            """, (is_in_stock, product_name, datetime.now(), product_id))
        else:
            cursor.execute("""
                UPDATE tracked_products 
                SET is_in_stock = ?, last_checked = ?
                WHERE id = ?
            """, (is_in_stock, datetime.now(), product_id))
        
        # Record in history
        cursor.execute("""
            INSERT INTO stock_history (tracked_product_id, was_in_stock)
            VALUES (?, ?)
        """, (product_id, is_in_stock))
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error updating stock: {e}")
    finally:
        conn.close()


def get_all_tracked_products() -> List[dict]:
    """Get all tracked products for background checking."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, user_id, sku, pincode, product_name, is_in_stock
        FROM tracked_products
    """)
    
    products = []
    for row in cursor.fetchall():
        products.append({
            'id': row['id'],
            'user_id': row['user_id'],
            'sku': row['sku'],
            'pincode': row['pincode'],
            'product_name': row['product_name'],
            'is_in_stock': bool(row['is_in_stock'])
        })
    
    conn.close()
    return products


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user information by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None
