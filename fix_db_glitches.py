#!/usr/bin/env python3
"""
Find and remove glitches from the market_snapshots database.

Glitch criteria:
1. [DISABLED] Bid = Ask (spread = 0 or <= $0.001)
2. UP and DOWN are equal when >$0.6 (excluding $0.5)
3. Sharp spikes: price changes >$0.2 in <2 seconds, then returns
4. Abnormally low prices: UP ask or DOWN ask < $0.04
5. UP + DOWN sum < 0.95 or > 1.15

Glitches are DELETED, not interpolated, because:
- Interpolation creates artificial data
- Deletion preserves data authenticity
- Markets are recorded every second, losing a few snapshots is not critical
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / '15m-synthetic' / 'db' / 'real-data.db'

def get_target_price(market_slug, conn):
    """Get target_price from metadata of the first market snapshot"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT metadata FROM market_snapshots
        WHERE market_slug = ?
        ORDER BY time_to_expiry DESC
        LIMIT 1
    """, (market_slug,))
    
    result = cursor.fetchone()
    if result and result[0]:
        try:
            import json
            metadata = json.loads(result[0])
            return metadata.get('target_price')
        except:
            pass
    return None


def is_extreme_price_valid(row, oracle_price, target_price):
    """
    Validates extreme price (<0.04) based on context.
    
    Extreme price is valid if:
    1. BTC is far from target (>$100) AND price is in the correct direction
    2. Last 100 seconds of market (time_to_expiry <= 100)
    
    Args:
        row: snapshot with prices
        oracle_price: current BTC price
        target_price: market target price
    
    Returns:
        True if price is valid (not a glitch)
    """
    up_ask = row['up_ask']
    down_ask = row['down_ask']
    time_to_expiry = row['time_to_expiry']
    
    # If no oracle or target, cannot validate - consider it a glitch
    if pd.isna(oracle_price) or target_price is None:
        return False
    
    distance = abs(oracle_price - target_price)
    
    # Check 1: Last 100 seconds - prices can be extreme
    if time_to_expiry <= 100:
        return True
    
    # Check 2: BTC is far from target
    if distance >= 100:
        # UP cheap (<0.04) is valid if BTC is BELOW target
        if up_ask < 0.04 and oracle_price < target_price:
            return True
        
        # DOWN cheap (<0.04) is valid if BTC is ABOVE target
        if down_ask < 0.04 and oracle_price > target_price:
            return True
    
    return False


def find_glitches(conn):
    """Find all glitches in the database"""
    print("Loading data from database...")
    
    # Load all snapshots (including oracle_price and metadata)
    df = pd.read_sql_query("""
        SELECT rowid as id, market_slug, dt, 
               up_bid, up_ask, up_mid,
               down_bid, down_ask, down_mid,
               time_to_expiry,
               oracle_price, binance_price
        FROM market_snapshots
        WHERE up_ask > 0 AND down_ask > 0
        ORDER BY market_slug, dt ASC
    """, conn)
    
    print(f"Loaded {len(df)} snapshots")
    
    df['ts'] = pd.to_datetime(df['dt'], format='ISO8601').astype('int64') // 10**9
    
    glitches = []
    
    print("\nSearching for glitches...")
    
    # Cache for target_price by market
    target_prices = {}
    
    # Cache for target_price by market
    target_prices = {}
    
    # Group by markets for time series analysis
    for market_slug, group in df.groupby('market_slug'):
        group = group.sort_values('ts').copy()
        
        # Get target_price for this market (once)
        if market_slug not in target_prices:
            target_prices[market_slug] = get_target_price(market_slug, conn)
        
        target_price = target_prices[market_slug]
        
        for idx in group.index:
            row = group.loc[idx]
            rowid = int(row['id'])
            
            # Get oracle_price
            oracle_price = row['oracle_price'] if pd.notna(row['oracle_price']) else row['binance_price']
            
            # GLITCH 1: Abnormally low prices (< $0.04) - CHECK WITH CONTEXT!
            if row['up_ask'] < 0.04 or row['down_ask'] < 0.04:
                # Check validity of extreme price
                if not is_extreme_price_valid(row, oracle_price, target_price):
                    glitches.append({
                        'rowid': rowid,
                        'market_slug': market_slug,
                        'dt': row['dt'],
                        'type': 'anomaly_low_price',
                        'details': f"UP ask=${row['up_ask']:.3f}, DOWN ask=${row['down_ask']:.3f}, TTE={row['time_to_expiry']}s",
                    })
                    continue  # Don't check other criteria for this snapshot
            
            # GLITCH 2: Bid = Ask (spread = 0 or very small)
            # DISABLED: Zero spread can be a valid market state
            # if abs(row['up_bid'] - row['up_ask']) <= 0.001 or abs(row['down_bid'] - row['down_ask']) <= 0.001:
            #     glitches.append({
            #         'rowid': rowid,
            #         'market_slug': market_slug,
            #         'dt': row['dt'],
            #         'type': 'zero_spread',
            #         'details': f"UP bid=${row['up_bid']:.3f} ask=${row['up_ask']:.3f}, DOWN bid=${row['down_bid']:.3f} ask=${row['down_ask']:.3f}",
            #     })
            #     continue
            
            # GLITCH 3: UP and DOWN are equal when >$0.6 (excluding $0.5)
            up_mid = row['up_mid']
            down_mid = row['down_mid']
            
            if abs(up_mid - down_mid) < 0.05 and up_mid > 0.6:
                glitches.append({
                    'rowid': rowid,
                    'market_slug': market_slug,
                    'dt': row['dt'],
                    'type': 'equal_prices',
                    'details': f"UP mid=${up_mid:.3f}, DOWN mid=${down_mid:.3f}",
                })
                continue
            
            # GLITCH 4: UP + DOWN sum is incorrect
            # Use ask prices (buy prices) as they are more important for us
            total = row['up_ask'] + row['down_ask']
            
            # Sum should be between $0.95 and $1.15 (usually >$1 due to spread)
            if total < 0.95 or total > 1.15:
                glitches.append({
                    'rowid': rowid,
                    'market_slug': market_slug,
                    'dt': row['dt'],
                    'type': 'invalid_sum',
                    'details': f"UP ask=${row['up_ask']:.3f} + DOWN ask=${row['down_ask']:.3f} = ${total:.3f}",
                })
                continue
            
            # GLITCH 5: Sharp spikes (check only if there are previous and next snapshots)
            group_list = group.index.tolist()
            idx_pos = group_list.index(idx)
            
            if idx_pos > 0 and idx_pos < len(group_list) - 1:
                prev_idx = group_list[idx_pos - 1]
                next_idx = group_list[idx_pos + 1]
                
                prev = group.loc[prev_idx]
                next_row = group.loc[next_idx]
                
                # Check time interval
                dt_prev = row['ts'] - prev['ts']
                dt_next = next_row['ts'] - row['ts']
                dt_total = next_row['ts'] - prev['ts']  # Total interval between prev and next
                
                # IMPORTANT: Check total interval to avoid counting spike after glitch removal
                # If >5 seconds passed between prev and next, it's not a spike, just different time points
                if dt_prev < 2 and dt_next < 2 and dt_total <= 5:  # Within 2 seconds each, and total interval <=5 sec
                    # Check DOWN ask (most important price for us)
                    down_ask_change_in = abs(row['down_ask'] - prev['down_ask'])
                    down_ask_change_out = abs(next_row['down_ask'] - row['down_ask'])
                    
                    # If price jumped >$0.2, then returned (threshold increased from $0.1 to $0.2)
                    if down_ask_change_in > 0.2 and down_ask_change_out > 0.2:
                        # Check that prices before and after are similar
                        if abs(prev['down_ask'] - next_row['down_ask']) < 0.1:
                            glitches.append({
                                'rowid': rowid,
                                'market_slug': market_slug,
                                'dt': row['dt'],
                                'type': 'spike',
                                'details': f"DOWN ask: {prev['down_ask']:.3f} -> {row['down_ask']:.3f} -> {next_row['down_ask']:.3f}",
                            })
                            continue
                    
                    # Also check UP ask
                    up_ask_change_in = abs(row['up_ask'] - prev['up_ask'])
                    up_ask_change_out = abs(next_row['up_ask'] - row['up_ask'])
                    
                    if up_ask_change_in > 0.2 and up_ask_change_out > 0.2:
                        if abs(prev['up_ask'] - next_row['up_ask']) < 0.1:
                            glitches.append({
                                'rowid': rowid,
                                'market_slug': market_slug,
                                'dt': row['dt'],
                                'type': 'spike',
                                'details': f"UP ask: {prev['up_ask']:.3f} -> {row['up_ask']:.3f} -> {next_row['up_ask']:.3f}",
                            })
    
    return pd.DataFrame(glitches)


def delete_glitches(conn, glitches_df, dry_run=True):
    """Delete glitches from the database"""
    if len(glitches_df) == 0:
        print("No glitches to delete")
        return
    
    print(f"\n{'='*100}")
    print(f"DELETING GLITCHES ({'DRY RUN' if dry_run else 'REAL'})")
    print(f"{'='*100}")
    
    cursor = conn.cursor()
    
    # Check current number of snapshots
    cursor.execute("SELECT COUNT(*) FROM market_snapshots")
    total_before = cursor.fetchone()[0]
    print(f"\nSnapshots in DB before deletion: {total_before}")
    print(f"Glitches to delete: {len(glitches_df)}")
    
    if not dry_run:
        # Delete glitches
        deleted = 0
        for idx, glitch in glitches_df.iterrows():
            market_slug = glitch['market_slug']
            dt = glitch['dt']
            
            cursor.execute("""
                DELETE FROM market_snapshots
                WHERE market_slug = ? AND dt = ?
            """, (market_slug, dt))
            
            deleted += cursor.rowcount
            
            if (idx + 1) % 1000 == 0:
                print(f"  Deleted {idx + 1}/{len(glitches_df)} glitches...")
        
        conn.commit()
        
        # Check result
        cursor.execute("SELECT COUNT(*) FROM market_snapshots")
        total_after = cursor.fetchone()[0]
        
        print(f"\n✅ Deleted {deleted} glitches")
        print(f"Snapshots in DB after deletion: {total_after}")
        print(f"Difference: {total_before - total_after}")
        
        # Check that markets remain intact
        cursor.execute("""
            SELECT market_slug, COUNT(*) as count
            FROM market_snapshots
            GROUP BY market_slug
            HAVING count < 100
            ORDER BY count
        """)
        
        small_markets = cursor.fetchall()
        if small_markets:
            print(f"\n⚠️  Markets with <100 snapshots: {len(small_markets)}")
            print("First 10:")
            for market, count in small_markets[:10]:
                print(f"  {market}: {count} snapshots")
        else:
            print(f"\n✅ All markets have sufficient snapshots")
    else:
        print(f"\n(DRY RUN: changes not applied)")
        print(f"Will be deleted: {len(glitches_df)} snapshots")
        print(f"Will remain: {total_before - len(glitches_df)} snapshots")


def main():
    print("="*100)
    print("SEARCH AND DELETE GLITCHES FROM DATABASE")
    print("="*100)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Find glitches
    glitches_df = find_glitches(conn)
    
    print(f"\n{'='*100}")
    print(f"GLITCHES FOUND: {len(glitches_df)}")
    print(f"{'='*100}")
    
    if len(glitches_df) > 0:
        # Statistics by type
        print("\nBy type:")
        for glitch_type, count in glitches_df['type'].value_counts().items():
            print(f"  {glitch_type}: {count}")
        
        # Save to CSV
        csv_path = 'glitches_found.csv'
        glitches_df.to_csv(csv_path, index=False)
        print(f"\n[OK] Glitches saved to {csv_path}")
        
        # Show first 20 glitches
        print(f"\nFirst 20 glitches:")
        print(f"{'#':<5} {'Type':<15} {'Market':<30} {'Time':<30} {'Details':<50}")
        print("-"*130)
        
        for idx, glitch in glitches_df.head(20).iterrows():
            print(f"{idx+1:<5} {glitch['type']:<15} {glitch['market_slug'][-30:]:<30} "
                  f"{glitch['dt'][-30:]:<30} {glitch['details']:<50}")
        
        # Ask whether to delete
        print(f"\n{'='*100}")
        response = input(f"Delete {len(glitches_df)} glitches? (yes/no/dry-run): ").strip().lower()
        
        if response == 'yes':
            delete_glitches(conn, glitches_df, dry_run=False)
        elif response == 'dry-run':
            delete_glitches(conn, glitches_df, dry_run=True)
        else:
            print("Cancelled")
    
    conn.close()


if __name__ == '__main__':
    main()
